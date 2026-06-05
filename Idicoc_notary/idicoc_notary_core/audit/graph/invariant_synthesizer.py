"""
Sintetizador de Invariantes Combinatorio - Fase 1 (Cold Loop).

Compila políticas textuales en matrices estáticas de token_ids prohibidos (W_bank).
Esta compilación ocurre UNA SOLA VEZ durante la inicialización del sistema.
Durante la Fase 3 (Hot Loop), el DeterministicMUXLogitsProcessor aplica
una máscara O(1) usando W_bank para garantizar contenencia de la red neuronal.

Especificación: IDICOC Standard-Zero, Sección 2.3 (Contención Sub-Simbólica)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("audit.invariant_synthesizer")


@dataclass
class InvariantToken:
    """Representación de un token individual prohibido."""

    token_id: int
    token_text: str
    source_policy: str
    policy_id: Optional[str] = None
    hardness: str = "soft"  # "soft" | "hard"
    priority: int = 1


@dataclass
class PolicyCompilationResult:
    """Resultado de la compilación de una política individual."""

    policy_id: Optional[str]
    policy_text: str
    forbidden_tokens: List[InvariantToken]
    compilation_status: str  # "success" | "warning" | "error"
    message: str


class InvariantSynthesizer:
    """
    Compilador determinista de políticas → matriz de tokens prohibidos (W_bank).

    Flujo:
    1. Lee políticas textuales (context_policies)
    2. Tokeniza cada política con el tokenizador de Llama
    3. Extrae conceptos violados y sus sinónimos
    4. Construye matriz indexada W_bank[token_id] = (hardness, priority)
    5. Persiste W_bank en memoria GPU para acceso O(1) en Phase 3
    """

    def __init__(
        self,
        tokenizer: Any,  # transformers.PreTrainedTokenizer (Llama)
        embedding_service: Optional[Any] = None,  # Para análisis semántico avanzado
    ) -> None:
        """
        Inicializa el sintetizador.

        Args:
            tokenizer: Tokenizador de Llama (transformers.AutoTokenizer)
            embedding_service: Servicio de embeddings opcional para análisis semántico
        """
        self.tokenizer = tokenizer
        self.embedding_service = embedding_service
        self.w_bank: Dict[int, Tuple[str, int]] = {}  # token_id → (hardness, priority)
        self.compilation_log: List[PolicyCompilationResult] = []
        self.vocab_size = len(tokenizer) if hasattr(tokenizer, "__len__") else tokenizer.vocab_size

        logger.info(
            f"[Invariant Synthesizer] Inicializado con tokenizador Llama. "
            f"Tamaño de vocabulario: {self.vocab_size}"
        )

    def compile_policies(
        self,
        policies: List[Dict[str, Any]],
        include_variants: bool = True,
        hardness_multiplier: float = 1.0,
    ) -> Dict[int, Tuple[str, int]]:
        """
        Compila una lista de políticas en matriz W_bank.

        Args:
            policies: Lista de dicts con {text, hardness, priority, ...}
            include_variants: Si True, genera variantes sintácticas de cada política
            hardness_multiplier: Escala de prioridad según dureza (soft=1.0, hard=2.0)

        Returns:
            Diccionario W_bank: {token_id: (hardness, priority)}
        """
        self.w_bank.clear()
        self.compilation_log.clear()

        logger.info(f"[Phase 1 - Cold Loop] Compilando {len(policies)} políticas...")

        total_tokens = 0
        hard_policies = sum(1 for p in policies if p.get("hardness") == "hard")
        soft_policies = len(policies) - hard_policies

        for policy in policies:
            result = self._compile_single_policy(
                policy,
                include_variants=include_variants,
                hardness_multiplier=hardness_multiplier,
            )
            self.compilation_log.append(result)
            total_tokens += len(result.forbidden_tokens)

        logger.info(
            f"[Phase 1 - Cold Loop] Compilación completada. "
            f"Matriz W_bank contiene {len(self.w_bank)} tokens prohibidos. "
            f"Políticas hard={hard_policies}, soft={soft_policies}, "
            f"Tokens únicos indexados={len(self.w_bank)}"
        )

        return self.w_bank

    def _compile_single_policy(
        self,
        policy: Dict[str, Any],
        include_variants: bool = True,
        hardness_multiplier: float = 1.0,
    ) -> PolicyCompilationResult:
        """Compila una política individual."""
        policy_text = policy.get("text", "")
        policy_id = policy.get("id") or policy.get("policy_id")
        hardness = policy.get("hardness", "soft")
        priority = int(policy.get("priority", 1))

        if not policy_text:
            return PolicyCompilationResult(
                policy_id=policy_id,
                policy_text=policy_text,
                forbidden_tokens=[],
                compilation_status="warning",
                message="Política vacía, ignorada.",
            )

        forbidden_tokens: List[InvariantToken] = []

        try:
            # Tokenizar la política base
            base_tokens = self._extract_concept_tokens(policy_text, policy_id, hardness, priority)
            forbidden_tokens.extend(base_tokens)

            # Si se solicita, generar variantes semánticas
            if include_variants and self.embedding_service:
                variant_tokens = self._generate_semantic_variants(
                    policy_text, policy_id, hardness, priority
                )
                forbidden_tokens.extend(variant_tokens)

            # Agregar tokens a W_bank
            for token_info in forbidden_tokens:
                priority_scaled = token_info.priority
                if hardness == "hard":
                    priority_scaled = int(priority_scaled * hardness_multiplier)

                # Si el token ya existe, mantener la máxima prioridad
                if token_info.token_id in self.w_bank:
                    existing_hardness, existing_priority = self.w_bank[token_info.token_id]
                    # Preferir "hard" sobre "soft"
                    new_hardness = (
                        "hard" if hardness == "hard" or existing_hardness == "hard" else "soft"
                    )
                    # Mantener máxima prioridad
                    new_priority = max(priority_scaled, existing_priority)
                    self.w_bank[token_info.token_id] = (new_hardness, new_priority)
                else:
                    self.w_bank[token_info.token_id] = (hardness, priority_scaled)

            return PolicyCompilationResult(
                policy_id=policy_id,
                policy_text=policy_text,
                forbidden_tokens=forbidden_tokens,
                compilation_status="success",
                message=f"Compilada exitosamente. {len(forbidden_tokens)} tokens prohibidos.",
            )

        except Exception as e:
            logger.error(f"Error compilando política {policy_id}: {e}")
            return PolicyCompilationResult(
                policy_id=policy_id,
                policy_text=policy_text,
                forbidden_tokens=[],
                compilation_status="error",
                message=f"Error durante compilación: {str(e)}",
            )

    def _extract_concept_tokens(
        self,
        text: str,
        policy_id: Optional[str],
        hardness: str,
        priority: int,
    ) -> List[InvariantToken]:
        """Extrae tokens de concepto clave de una política."""
        tokens = []

        try:
            # Tokenizar directamente
            token_ids = self.tokenizer.encode(text, add_special_tokens=False)

            for token_id in token_ids:
                # Evitar tokens especiales o muy raros
                if token_id >= self.vocab_size or token_id < 0:
                    continue

                # Decodificar para logging
                try:
                    token_text = self.tokenizer.decode([token_id])
                except:
                    token_text = f"<UNK:{token_id}>"

                token = InvariantToken(
                    token_id=token_id,
                    token_text=token_text,
                    source_policy=text[:50] + ("..." if len(text) > 50 else ""),
                    policy_id=policy_id,
                    hardness=hardness,
                    priority=priority,
                )
                tokens.append(token)

        except Exception as e:
            logger.warning(f"Error extrayendo tokens de '{text}': {e}")

        return tokens

    def _generate_semantic_variants(
        self,
        policy_text: str,
        policy_id: Optional[str],
        hardness: str,
        priority: int,
    ) -> List[InvariantToken]:
        """Genera variantes semánticas de una política (requiere embedding_service)."""
        variants = []

        if not self.embedding_service:
            return variants

        try:
            # Estrategia simple: tokenizar sinónimos/variantes comunes
            # Esto es un placeholder; en producción se usaría más lógica sofisticada
            synthetic_variants = self._generate_synthetic_paraphrases(policy_text)

            for variant in synthetic_variants:
                token_ids = self.tokenizer.encode(variant, add_special_tokens=False)
                for token_id in token_ids[:5]:  # Limitar a primeros 5 tokens por variante
                    if token_id not in [t.token_id for t in variants]:
                        token_text = self.tokenizer.decode([token_id])
                        token = InvariantToken(
                            token_id=token_id,
                            token_text=token_text,
                            source_policy=f"variant:{policy_text[:40]}...",
                            policy_id=policy_id,
                            hardness=hardness,
                            priority=max(
                                1, priority - 1
                            ),  # Variantes con prioridad ligeramente menor
                        )
                        variants.append(token)

        except Exception as e:
            logger.warning(f"Error generando variantes de '{policy_text}': {e}")

        return variants

    def _generate_synthetic_paraphrases(self, text: str) -> List[str]:
        """Genera paráfrasis sintéticas de una política (estrategia placeholder)."""
        # Estrategia simple: invertir palabras clave, cambiar orden, etc.
        # En producción, esto usaría modelos T5 o similares
        paraphrases = []

        words = text.split()
        if len(words) > 2:
            # Variante 1: orden invertido
            paraphrases.append(" ".join(reversed(words)))
            # Variante 2: primeras palabras duplicadas
            paraphrases.append(" ".join(words[:2]) + " " + text)

        return paraphrases

    def get_w_bank_mask(self) -> Dict[int, Tuple[str, int]]:
        """
        Retorna la matriz W_bank compilada.

        Returns:
            Dict mapeando token_id → (hardness: str, priority: int)
        """
        return self.w_bank.copy()

    def get_forbidden_token_ids(self, hardness: Optional[str] = None) -> Set[int]:
        """
        Retorna conjunto de token_ids prohibidos, opcionalmente filtrados por dureza.

        Args:
            hardness: Filtrar por "hard" | "soft" | None (todos)

        Returns:
            Set de token_ids prohibidos
        """
        if hardness is None:
            return set(self.w_bank.keys())

        return {token_id for token_id, (h, _) in self.w_bank.items() if h == hardness}

    def get_compilation_report(self) -> Dict[str, Any]:
        """Retorna reporte detallado de compilación."""
        successful = sum(1 for r in self.compilation_log if r.compilation_status == "success")
        warnings = sum(1 for r in self.compilation_log if r.compilation_status == "warning")
        errors = sum(1 for r in self.compilation_log if r.compilation_status == "error")

        return {
            "total_policies": len(self.compilation_log),
            "successful": successful,
            "warnings": warnings,
            "errors": errors,
            "w_bank_size": len(self.w_bank),
            "unique_forbidden_tokens": len(self.w_bank),
            "compilation_log": [
                {
                    "policy_id": r.policy_id,
                    "status": r.compilation_status,
                    "tokens_count": len(r.forbidden_tokens),
                    "message": r.message,
                }
                for r in self.compilation_log
            ],
        }
