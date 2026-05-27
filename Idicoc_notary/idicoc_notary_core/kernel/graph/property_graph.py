from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set


class PropertyGraph:
    """Estructura de grafo de propiedades para axiomas y reglas en el núcleo."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._conflicts: List[Dict[str, Any]] = []

    # ──────────────────────────────────────────────────────────────────────────
    # API pública — gestión del grafo
    # ──────────────────────────────────────────────────────────────────────────

    def add_axiom(self, identifier: str, axiom: Dict[str, Any]) -> None:
        """Añade un axioma identificado al grafo."""
        self.nodes[identifier] = axiom

    def add_edge(self, source: str, target: str, relation: str) -> None:
        """Añade una arista entre dos axiomas."""
        self.edges.append({"source": source, "target": target, "relation": relation})

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """Detecta conflictos entre axiomas (comprueba polarity en mismo sujeto/objeto)."""
        conflicts = []
        nodes_list = list(self.nodes.items())
        for i, (id1, axiom1) in enumerate(nodes_list):
            for id2, axiom2 in nodes_list[i + 1:]:
                if (
                    axiom1.get("subject") == axiom2.get("subject")
                    and axiom1.get("object") == axiom2.get("object")
                    and axiom1.get("polarity") != axiom2.get("polarity")
                ):
                    conflicts.append({"axiom1": id1, "axiom2": id2, "reason": "opposite_polarity"})
        self._conflicts = conflicts
        return conflicts

    def validate(self, raw_input: Any) -> bool:
        """Validación estructural básica."""
        return len(self._conflicts) == 0

    def get_active_axioms(self) -> List[Dict[str, Any]]:
        """Retorna todos los axiomas activos."""
        return list(self.nodes.values())

    def get_conflicts(self) -> List[Dict[str, Any]]:
        """Retorna los últimos conflictos detectados."""
        return self._conflicts

    def compute_axiom_density(self) -> float:
        """Calcula la densidad de axiomas en el grafo."""
        if not self.nodes:
            return 0.0
        num_nodes = len(self.nodes)
        num_edges = len(self.edges)
        max_edges = num_nodes * (num_nodes - 1) // 2
        if max_edges == 0:
            return 0.0
        return num_edges / max_edges

    def clear(self) -> None:
        """Limpia el grafo (para testing o reinicio)."""
        self.nodes.clear()
        self.edges.clear()
        self._conflicts.clear()

    # ──────────────────────────────────────────────────────────────────────────
    # evaluate(y) — dissonancia lógica
    # ──────────────────────────────────────────────────────────────────────────

    def evaluate(self, y: Any) -> float:
        """
        Evalúa la disonancia lógica de un estado candidato ``y`` contra los
        axiomas no-temporales activos en el grafo.

        Estrategia (determinista, sin modelos externos):
        ─────────────────────────────────────────────────
        1.  Representación de ``y`` como conjunto de tokens (``y_tokens``).
        2.  Para cada axioma lógico/factual/world/protocol:
            a. Si el axioma tiene un embedding precalculado (campo ``embedding``),
               se usa distancia coseno contra el embedding de ``y`` (si ``y``
               también es un vector numérico). Puntuación ∈ [0, 1].
            b. Si no, se calcula la similitud de Jaccard entre los tokens del
               axioma y los tokens de ``y``. Puntuación de violación =
               ``1 − jaccard``.
        3.  La penalización final de cada axioma se multiplica por su ``weight``,
            donde ``weight = priority / 10 * hardness_mult``.
        4.  Resultado = media ponderada de penalizaciones, normalizada a [0, 1].

        Polaridad:
        - **affirmative**: violación si ``y`` NO satisface el axioma
          (distancia alta o jaccard baja).
        - **negative**:   violación si ``y``  satisface el axioma
          (distancia baja o jaccard alta — el axioma es una prohibición).

        Returns:
            float en [0.0, 1.0]. 0.0 = ninguna violación. 1.0 = violación total.
        """
        axioms = [ax for ax in self.nodes.values() if ax.get("axiom_type") != "temporal"]
        if not axioms:
            return 0.0

        y_tokens = self._tokenize(self._to_str(y))
        y_vec = self._to_vec(y)  # None si y no es numérico

        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in axioms:
            raw_penalty = self._logical_penalty(y_tokens, y_vec, ax)
            weight = self._axiom_weight(ax)
            weighted_penalty += raw_penalty * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        return min(1.0, weighted_penalty / total_weight)

    # ──────────────────────────────────────────────────────────────────────────
    # compute_temporal(y) — dissonancia temporal
    # ──────────────────────────────────────────────────────────────────────────

    def compute_temporal(self, y: Any) -> float:
        """
        Evalúa la disonancia temporal del estado candidato ``y`` contra los
        axiomas con ``axiom_type == 'temporal'`` activos en el grafo.

        Estrategia (determinista):
        ──────────────────────────
        Para cada axioma temporal se verifican las siguientes claves opcionales:

        ``valid_from`` (str ISO-8601 o float epoch)
            El axioma solo es válido a partir de esta fecha.
        ``valid_until`` (str ISO-8601 o float epoch)
            El axioma deja de ser válido a partir de esta fecha.
        ``ttl_seconds`` (float)
            Tiempo de vida en segundos desde ``valid_from`` o desde
            ``timestamp`` del axioma. Si el tiempo actual supera
            ``valid_from + ttl_seconds``, el axioma ha expirado.

        Puntuación de violación temporal:
        - Si el axioma está vigente → 0.0.
        - Si ha expirado o aún no es válido → 1.0.
        - Si el tiempo se puede medir y hay un desfase parcial, se devuelve
          la fracción del desfase sobre el total de la ventana (penalty ∈ (0,1]).

        La puntuación final se calcula como media ponderada por ``priority`` y
        ``hardness``.

        Returns:
            float en [0.0, 1.0]. 0.0 = todas las restricciones temporales ok.
        """
        temporal_axioms = [
            ax for ax in self.nodes.values() if ax.get("axiom_type") == "temporal"
        ]
        if not temporal_axioms:
            return 0.0

        now = datetime.now(timezone.utc)

        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in temporal_axioms:
            raw_penalty = self._temporal_penalty(ax, now)
            weight = self._axiom_weight(ax)
            weighted_penalty += raw_penalty * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        return min(1.0, weighted_penalty / total_weight)

    # Alias para compatibilidad con la interfaz esperada por StructuralDissonanceStrategy
    compute_d_temporal = compute_temporal

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers internos
    # ──────────────────────────────────────────────────────────────────────────

    # ── Texto / tokens ────────────────────────────────────────────────────────

    @staticmethod
    def _to_str(y: Any) -> str:
        """Convierte ``y`` a su representación textual canónica."""
        if y is None:
            return ""
        if isinstance(y, str):
            return y
        if hasattr(y, "data"):
            return str(y.data)
        if hasattr(y, "source_text"):
            return str(y.source_text)
        return str(y)

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        """Tokeniza texto en minúsculas eliminando puntuación básica."""
        import re
        tokens = re.split(r"[\s,;:.!?()\[\]{}'\"]+", text.lower())
        return {t for t in tokens if t}

    @staticmethod
    def _axiom_text(axiom: Dict[str, Any]) -> str:
        """Construye la representación textual canónica de un axioma."""
        parts = [
            str(axiom.get("source_text", "")),
            str(axiom.get("subject", "")),
            str(axiom.get("predicate", "")),
            str(axiom.get("object", "")),
        ]
        return " ".join(p for p in parts if p and p != "None")

    # ── Vector numérico ───────────────────────────────────────────────────────

    @staticmethod
    def _to_vec(y: Any) -> Optional[list]:
        """
        Extrae la representación vectorial de ``y`` si está disponible.
        Retorna None si ``y`` no es numérico.
        """
        try:
            import numpy as np
            candidate = getattr(y, "measure_vector", getattr(y, "distribution", y))
            arr = np.asarray(candidate, dtype=float)
            if arr.ndim == 1 and arr.size > 0:
                return arr.tolist()
        except Exception:
            pass
        return None

    @staticmethod
    def _cosine_distance(a: list, b: list) -> float:
        """Distancia coseno en [0, 1]. 0 = idénticos, 1 = ortogonales."""
        import math
        if len(a) != len(b):
            # Padding con ceros al tamaño mayor
            n = max(len(a), len(b))
            a = a + [0.0] * (n - len(a))
            b = b + [0.0] * (n - len(b))
        dot = sum(x * z for x, z in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a < 1e-12 or norm_b < 1e-12:
            return 1.0
        cosine_sim = dot / (norm_a * norm_b)
        # Clamp por posibles errores de punto flotante
        return 1.0 - max(-1.0, min(1.0, cosine_sim))

    # ── Jaccard ───────────────────────────────────────────────────────────────

    @staticmethod
    def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
        """Similitud de Jaccard entre dos conjuntos de tokens."""
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0

    # ── Penalización lógica ───────────────────────────────────────────────────

    def _logical_penalty(
        self,
        y_tokens: Set[str],
        y_vec: Optional[list],
        axiom: Dict[str, Any],
    ) -> float:
        """
        Penalización de un axioma lógico/factual sobre ``y`` ∈ [0, 1].

        Algoritmo:
        1. Si el axioma tiene un ``embedding`` (lista de floats) y ``y`` también
           es vectorial → distancia coseno.
        2. Si el axioma tiene ``embedding`` pero ``y`` es texto → Jaccard entre
           los tokens del axioma y los de ``y`` (sin usar el embedding del axioma
           como no hay representación vectorial de y).
        3. Caso general: Jaccard sobre tokens.

        La penalización cruda (∈ [0,1]) se invierte según la polaridad:
        - affirmative: penalización = 1 − similitud  (queremos que y sea similar)
        - negative:    penalización = similitud       (queremos que y sea diferente)
        """
        polarity = axiom.get("polarity", "affirmative")
        ax_embedding: Optional[list] = axiom.get("embedding")  # precalculado, si existe

        # ── Caso 1: embeddings disponibles y y es vectorial ──
        if ax_embedding is not None and y_vec is not None:
            dist = self._cosine_distance(y_vec, ax_embedding)
            similarity = 1.0 - dist
        # ── Caso 2/3: Jaccard sobre tokens ──
        else:
            ax_tokens = self._tokenize(self._axiom_text(axiom))
            if not ax_tokens:
                return 0.0
            similarity = self._jaccard(y_tokens, ax_tokens)

        if polarity == "affirmative":
            return 1.0 - similarity   # violación si y NO es similar al axioma
        else:
            return similarity          # violación si y SÍ coincide (prohibición)

    # ── Penalización temporal ─────────────────────────────────────────────────

    def _temporal_penalty(self, axiom: Dict[str, Any], now: datetime) -> float:
        """
        Calcula la penalización temporal de un axioma en el instante ``now``.

        Soporta las claves:
          valid_from   (ISO-8601 str | epoch float | None)
          valid_until  (ISO-8601 str | epoch float | None)
          ttl_seconds  (float | None)  — relativo a valid_from o timestamp

        Retorna:
          0.0 — el axioma está vigente.
          1.0 — el axioma ha expirado o aún no es válido.
          valor ∈ (0,1) — violación parcial proporcional al desfase temporal.
        """
        valid_from = self._parse_dt(axiom.get("valid_from"))
        valid_until = self._parse_dt(axiom.get("valid_until"))

        # Derivar valid_until desde ttl_seconds si no está explícito
        if valid_until is None and axiom.get("ttl_seconds") is not None:
            base = valid_from or self._parse_dt(axiom.get("timestamp"))
            if base is not None:
                try:
                    ttl = float(axiom["ttl_seconds"])
                    from datetime import timedelta
                    valid_until = base + timedelta(seconds=ttl)
                except (ValueError, TypeError):
                    pass

        # Si no hay ninguna restricción temporal definida → sin violación
        if valid_from is None and valid_until is None:
            return 0.0

        # ── Comprobación valid_from ──
        if valid_from is not None and now < valid_from:
            # El axioma aún no ha entrado en vigor
            lag = (valid_from - now).total_seconds()
            # Penalización proporcional: cuanto más lejos, más violación
            # Normalizamos respecto a la ventana total (si la hay) o 86400 s (1 día)
            if valid_until is not None:
                window = max(1.0, (valid_until - valid_from).total_seconds())
            else:
                window = 86400.0
            return min(1.0, lag / window)

        # ── Comprobación valid_until ──
        if valid_until is not None and now > valid_until:
            # El axioma ha expirado
            overrun = (now - valid_until).total_seconds()
            if valid_from is not None:
                window = max(1.0, (valid_until - valid_from).total_seconds())
            else:
                window = 86400.0
            return min(1.0, overrun / window)

        # Dentro de la ventana → sin violación
        return 0.0

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        """Convierte str ISO-8601 o float epoch a datetime UTC, o None."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    # ── Peso del axioma ───────────────────────────────────────────────────────

    @staticmethod
    def _axiom_weight(axiom: Dict[str, Any]) -> float:
        """
        Calcula el peso de un axioma para la media ponderada.

        peso = (priority / 10) × hardness_mult
        - priority: int [1..10], por defecto 1
        - hardness_mult: 2.0 para 'hard', 1.0 para 'soft'
        """
        priority = max(1, min(10, int(axiom.get("priority", 1))))
        hardness_mult = 2.0 if axiom.get("hardness") == "hard" else 1.0
        return (priority / 10.0) * hardness_mult
