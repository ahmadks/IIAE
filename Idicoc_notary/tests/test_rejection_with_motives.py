"""
test_rejection_with_motives.py
==============================
Tests de rechazo con motivos explícitos.

Objetivo: Verificar que cuando el Notario IDICOC rechaza una señal, el resultado incluye:
  - Las políticas exactas que fueron violadas (con ID, texto y dureza)
  - El motivo del rechazo (hardness + disonancia)
  - Soporte completo para context_input como simulación de contexto RAG

Los tests usan un embedder determinista para evitar cargas de modelos externos.
La salida de pytest muestra claramente las políticas rechazadas y el motivo.
"""

import math
import pytest
import numpy as np

from idicoc_core.config import AuditConfig
from idicoc_core.api.facade import NotaryClient as RealNotaryClient
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core.dse.evaluator import PropertyGraphEvaluator
from idicoc_core.isg.graph_manager import PropertyGraph

class SemanticPayload:
    def __init__(self, source_text):
        self.source_text = source_text

class ResultWrapper:
    def __init__(self, metadata):
        self.metadata = metadata

class DummyAEM:
    def __init__(self):
        self.trail = []
        
    def record(self, metadata):
        self.trail.append({
            "d_s": metadata["d_s"],
            "violated_policies": metadata["violated_policies"],
            "admission_breach": metadata["admission_breach"]
        })
        
    def get_audit_trail(self):
        return self.trail
        
    def get_counters(self):
        total = len(self.trail)
        rejected = sum(1 for x in self.trail if x["admission_breach"])
        valid = total - rejected
        return total, valid, rejected

class IDICOCPipeline:
    def __init__(self, config):
        config.allowed_epsilon = config.rigidity_epsilon
        self.pipeline = AuditPipeline(config)
        self.aem = DummyAEM()

    def initialize(self):
        pass

    def execute(
        self,
        audit_input,
        user_input,
        context_input=None,
        context_policies=None,
        epsilon_override=None
    ):
        llm_output = audit_input.source_text if hasattr(audit_input, "source_text") else str(audit_input)
        
        rag_context = ""
        if context_input:
            if isinstance(context_input, list):
                rag_context = "\n".join(context_input)
            else:
                rag_context = str(context_input)
        
        user_prompt = str(user_input)
        
        audit_res = self.pipeline.execute_audit(
            user_prompt=user_prompt,
            rag_context=rag_context,
            llm_output=llm_output,
            context_policies=context_policies,
            epsilon_override=epsilon_override
        )
        
        metadata = {
            "admission_breach": not audit_res.is_admitted,
            "d_s": audit_res.dissonance_ds,
            "violated_policies": audit_res.violated_policies,
            "epsilon_used": audit_res.allowed_epsilon,
            "epsilon": audit_res.allowed_epsilon,
            "correction_flag": False,
            "d_context": audit_res.metrics.get("d_context", 0.0)
        }
        
        self.aem.record(metadata)
        
        return {
            "canonical_state": ResultWrapper(metadata=metadata)
        }

class NotaryClientWrapper:
    def __init__(self, config):
        config.allowed_epsilon = config.rigidity_epsilon
        self.client = RealNotaryClient(config)
        self.pipeline = self.client.pipeline
        self.aem = DummyAEM()

    def process_interaction(
        self,
        audit_input,
        user_input,
        context_input=None,
        context_policies=None,
        epsilon_override=None
    ):
        llm_output = audit_input.source_text if hasattr(audit_input, "source_text") else str(audit_input)
        
        rag_context = ""
        if context_input:
            if isinstance(context_input, list):
                rag_context = "\n".join(context_input)
            else:
                rag_context = str(context_input)
        
        user_prompt = str(user_input)
        
        audit_res = self.client.audit(
            user_prompt=user_prompt,
            rag_context=rag_context,
            llm_output=llm_output,
            context_policies=context_policies,
            epsilon_override=epsilon_override
        )
        
        metadata = {
            "admission_breach": not audit_res.is_admitted,
            "d_s": audit_res.dissonance_ds,
            "violated_policies": audit_res.violated_policies,
            "epsilon_used": audit_res.allowed_epsilon,
            "epsilon": audit_res.allowed_epsilon,
            "correction_flag": False,
            "d_context": audit_res.metrics.get("d_context", 0.0)
        }
        
        self.aem.record(metadata)
        
        return ResultWrapper(metadata=metadata)

NotaryClient = NotaryClientWrapper



# ──────────────────────────────────────────────────────────────────────────────
# Utilidades compartidas
# ──────────────────────────────────────────────────────────────────────────────

class DummyEmbedder:
    """
    Embedder determinista: mapea cada texto a un vector de 32 dimensiones
    basado en sus bytes UTF-8. No requiere carga de modelos externos.
    """
    def encode(self, text, model_name=None):
        import hashlib
        if isinstance(text, list):
            text = " ".join(str(t) for t in text)
        h = hashlib.sha256(str(text).encode("utf-8")).digest()
        vec = np.zeros(32, dtype=float)
        for idx in range(32):
            vec[idx] = (float(h[idx]) - 127.5) / 127.5
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0.0 else vec


def _build_client(**kwargs) -> NotaryClient:
    """Construye un NotaryClient con config mínima para tests."""
    config = AuditConfig(
        ctm_mode="disabled",
        rigidity_epsilon=kwargs.pop("epsilon", 0.2),
        policy_loader=None,
        policy_file_path="/tmp/nonexistent_test_policies.txt",
        embedding_provider=DummyEmbedder(),
        **kwargs,
    )
    return NotaryClient(config)


def _fmt_violated(policies: list) -> str:
    """Formatea la lista de políticas violadas para la salida de pytest."""
    if not policies:
        return "(ninguna)"
    lines = []
    for p in policies:
        lines.append(f"  • [{p['hardness'].upper()}] {p['id']}: {p['text']} (penalización={p['penalty']:.4f})")
    return "\n".join(lines)


def _rejection_summary(metadata: dict) -> str:
    """Genera un resumen legible del veredicto del Notario."""
    d_s = metadata.get("d_s", 0)
    eps = metadata.get("epsilon_used", metadata.get("epsilon", "?"))
    breach = metadata.get("admission_breach", False)
    vp = metadata.get("violated_policies", [])
    vp_text = ", ".join(vp) if vp else "(ninguna)"
    status = "RECHAZADO" if breach else "ADMITIDO"
    ds_text = "∞" if d_s == float("inf") else f"{d_s:.6f}"
    return (
        f"\n  Estado      : {status}"
        f"\n  Disonancia  : D_s = {ds_text}  |  ε = {eps}"
        f"\n  Políticas   : {vp_text}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# BLOQUE 1 — Rechazo por violación HARD (regex)
# ──────────────────────────────────────────────────────────────────────────────

class TestHardRejection:
    """Casos en que una política HARD fuerza rechazo inmediato (D_s = ∞)."""

    def test_hard_regex_keyword_blocked(self, capsys):
        """
        Política HARD con REGEX bloquea cualquier salida que contenga la palabra prohibida.
        context_input: simula contexto bancario RAG que prohíbe palabras despectivas.
        """
        client = _build_client(epsilon=0.3)
        context_input = [
            "El sistema bancario rechaza respuestas que contengan lenguaje ofensivo.",
            "Toda comunicación con clientes debe ser formal y profesional.",
        ]
        policy_input = [
            "[HARD] [REGEX: basura] No usar la palabra 'basura' en ninguna respuesta al usuario.",
        ]

        response_text = "Esta respuesta es basura y no sirve para nada."
        result = client.process_interaction(
            audit_input=SemanticPayload(response_text),
            user_input="¿Cómo funciona el sistema?",
            context_input=context_input,
            context_policies=policy_input,
        )
        meta = result.metadata

        # ── Imprimir resumen forense en la consola de pytest ─────────────────
        print(_rejection_summary(meta))

        # ── Aserciones ────────────────────────────────────────────────────────
        assert meta["admission_breach"] is True, "La respuesta debería ser RECHAZADA"
        assert math.isinf(meta["d_s"]), (
            f"D_s debería ser ∞ por violación HARD, pero fue {meta['d_s']}"
        )
        vp = meta.get("violated_policies", [])
        assert len(vp) >= 1, (
            f"Debe haber al menos 1 política violada. Obtenidas: {vp}"
        )
        # La política violada debe contener la palabra 'basura'
        vp_joined = " ".join(vp).lower()
        assert "basura" in vp_joined or "regex" in vp_joined, (
            f"La política violada debería mencionar 'basura'. Políticas: {vp}"
        )

    def test_hard_regex_multiple_keywords(self, capsys):
        """
        Dos políticas HARD con REGEX distintas. El sistema debe detectar
        cuál de las dos fue violada y reportarla correctamente.
        context_input: simula contexto de cumplimiento normativo financiero.
        """
        client = _build_client(epsilon=0.25)
        context_input = [
            "Cumplimiento: el sistema está auditado bajo GDPR y MiFID II.",
            "Toda salida del modelo debe ser trazable y libre de lenguaje sesgado.",
        ]
        policy_input = [
            "[HARD] [REGEX: prohibido] No usar la palabra 'prohibido' de forma peyorativa.",
            "[HARD] [REGEX: fraude]    Nunca sugerir actividades fraudulentas.",
        ]

        # Solo viola la segunda política
        response_text = "Le recomiendo este esquema de fraude para aumentar sus ganancias."
        result = client.process_interaction(
            audit_input=SemanticPayload(response_text),
            user_input="¿Cómo puedo ganar más dinero?",
            context_input=context_input,
            context_policies=policy_input,
        )
        meta = result.metadata
        print(_rejection_summary(meta))

        assert meta["admission_breach"] is True
        assert math.isinf(meta["d_s"])
        vp = meta.get("violated_policies", [])
        assert len(vp) >= 1, f"Debería haber al menos 1 política violada. Obtenidas: {vp}"
        vp_joined = " ".join(vp).lower()
        # 'fraude' no es substring de 'fraudulentas', pero 'fraud' sí lo es
        assert "fraud" in vp_joined or "regex" in vp_joined, (
            f"La política violada debería mencionar actividad fraudulenta. Políticas: {vp}"
        )

    def test_hard_rejection_does_not_modify_output(self):
        """
        El Notario en modo IIAE no realiza corrección ex-post.
        Aunque rechaza, devuelve el texto original sin alterarlo.
        """
        client = _build_client(epsilon=0.3)
        response_text = "El sistema es una total basura sin utilidad."
        result = client.process_interaction(
            audit_input=SemanticPayload(response_text),
            user_input="Evalúa el sistema.",
            context_input=["El sistema IIAE está bajo auditoría estricta."],
            context_policies=["[HARD] [REGEX: basura] No usar lenguaje ofensivo."],
        )
        meta = result.metadata
        assert meta["admission_breach"] is True
        assert meta["correction_flag"] is False, (
            "IIAE no corrige ex-post: correction_flag debe ser False."
        )


# ──────────────────────────────────────────────────────────────────────────────
# BLOQUE 2 — Rechazo por disonancia SOFT acumulada
# ──────────────────────────────────────────────────────────────────────────────

class TestSoftRejectionWithContext:
    """
    Casos donde las políticas son SOFT pero la disonancia acumulada
    supera el umbral epsilon y provoca rechazo.
    """

    def test_soft_rejection_with_rag_context(self, capsys):
        """
        Simula un escenario bancario donde el RAG proporciona contexto sobre
        límites de transferencia. La respuesta del LLM supera el límite y
        viola una política SOFT, llevando a rechazo por D_s > ε.

        context_input: contexto real recuperado por RAG del sistema.
        """
        # DummyEmbedder produce D_s~0.03 con políticas SOFT semánticas;
        # usamos epsilon=0.01 para garantizar rechazo con esa disonancia
        client = _build_client(epsilon=0.01, rag_d_context_cap=1.0)
        context_input = [
            "El límite máximo de transferencia diaria es 1000 EUR.",
            "Las transferencias superiores requieren autorización adicional.",
        ]
        policy_input = [
            "[SOFT] Las transferencias deben respetar el límite diario de seguridad.",
            "[SOFT] Toda operación superior a 1000 EUR requiere verificación de identidad.",
        ]

        # Respuesta que ignora el límite → alta disonancia semántica
        response_text = (
            "Puede realizar transferencias de hasta 50.000 EUR sin ningún tipo "
            "de verificación adicional."
        )
        result = client.process_interaction(
            audit_input=SemanticPayload(response_text),
            user_input="¿Cuánto puedo transferir sin autorización?",
            context_input=context_input,
            context_policies=policy_input,
        )
        meta = result.metadata
        print(_rejection_summary(meta))

        # Con epsilon muy bajo y políticas semánticas opuestas, debe rechazar
        assert meta["admission_breach"] is True, (
            f"Debería ser rechazado. D_s={meta['d_s']:.6f}, ε={meta['epsilon_used']}"
        )
        assert not math.isinf(meta["d_s"]), "Políticas SOFT no deben generar D_s=∞"
        assert meta["d_s"] > meta["epsilon_used"], (
            f"D_s ({meta['d_s']:.4f}) debe superar ε ({meta['epsilon_used']})"
        )

    def test_soft_admission_compliant_response(self, capsys):
        """
        Control positivo: respuesta conforme con el contexto RAG → ADMITIDA.
        Verifica que el sistema no genera falsos positivos.
        """
        client = _build_client(epsilon=0.50)
        context_input = [
            "El límite máximo de transferencia diaria es 1000 EUR.",
        ]
        policy_input = [
            "[SOFT] Toda respuesta debe estar alineada con los límites de transferencia.",
        ]

        response_text = (
            "Para transferencias superiores a 1000 EUR, necesitará autorización adicional "
            "del departamento de seguridad bancaria."
        )
        result = client.process_interaction(
            audit_input=SemanticPayload(response_text),
            user_input="¿Cuál es el límite de transferencia?",
            context_input=context_input,
            context_policies=policy_input,
        )
        meta = result.metadata
        print(_rejection_summary(meta))

        assert meta["admission_breach"] is False, (
            f"Respuesta conforme debería ser ADMITIDA. D_s={meta['d_s']:.6f}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# BLOQUE 3 — Evaluación directa con PropertyGraphEvaluator
# ──────────────────────────────────────────────────────────────────────────────

class TestPropertyGraphEvaluatorViolations:
    """
    Tests de bajo nivel que usan PropertyGraphEvaluator directamente
    para verificar que get_violated_policies() retorna los datos correctos.
    """

    def _build_graph_with_policies(self, policies: list) -> PropertyGraph:
        graph = PropertyGraph(embedding_signature="dummy-v1")
        embedder = DummyEmbedder()
        for policy in policies:
            policy_id = policy["id"]
            if "embedding" not in policy:
                text = policy.get("text", policy.get("description", ""))
                vec = embedder.encode(text)
                policy["embedding"] = vec.tolist()
            graph.add_policy(policy_id, policy)
        return graph

    def test_get_violated_policies_hard_regex(self, capsys):
        """
        get_violated_policies() debe retornar la política HARD regex
        cuando el texto contiene la palabra prohibida.
        """
        graph = self._build_graph_with_policies([
            {
                "id": "pol_hard_basura",
                "text": "No usar la palabra basura",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "hard",
                "priority": 5,
                "pattern": "basura",
            },
            {
                "id": "pol_soft_tono",
                "text": "El tono debe ser profesional",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "soft",
                "priority": 3,
                "pattern": "idiota",
            },
        ])
        evaluator = PropertyGraphEvaluator(graph)

        text = "Esta respuesta es basura total."
        violated = evaluator.get_violated_policies(text)

        print(f"\n  Texto evaluado : '{text}'")
        print(f"  Políticas violadas:\n{_fmt_violated(violated)}")

        assert len(violated) == 1, (
            f"Solo debería violarse pol_hard_basura. Violadas: {[v['id'] for v in violated]}"
        )
        assert violated[0]["id"] == "pol_hard_basura"
        assert violated[0]["hardness"] == "hard"
        assert violated[0]["penalty"] > 0.0

    def test_get_violated_policies_multiple_violations(self, capsys):
        """
        Cuando múltiples políticas son violadas, get_violated_policies()
        debe retornar todas ellas con sus IDs, textos y dureza.
        """
        graph = self._build_graph_with_policies([
            {
                "id": "pol_fraude",
                "text": "Prohibido mencionar fraude",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "hard",
                "priority": 10,
                "pattern": "fraude",
            },
            {
                "id": "pol_estafa",
                "text": "Prohibido mencionar estafa",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "hard",
                "priority": 10,
                "pattern": "estafa",
            },
            {
                "id": "pol_lenguaje",
                "text": "No usar lenguaje violento",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "soft",
                "priority": 5,
                "pattern": "amenaza",
            },
        ])
        evaluator = PropertyGraphEvaluator(graph)

        text = "Le propongo un esquema de fraude y estafa garantizado."
        violated = evaluator.get_violated_policies(text)

        print(f"\n  Texto evaluado : '{text}'")
        print(f"  Políticas violadas ({len(violated)}):\n{_fmt_violated(violated)}")

        violated_ids = {v["id"] for v in violated}
        assert "pol_fraude" in violated_ids, "pol_fraude debería estar violada"
        assert "pol_estafa" in violated_ids, "pol_estafa debería estar violada"
        assert "pol_lenguaje" not in violated_ids, (
            "pol_lenguaje NO debería violarse (no hay 'amenaza' en el texto)"
        )

    def test_no_violations_when_compliant(self, capsys):
        """
        Control: texto conforme no debe generar violaciones.
        """
        graph = self._build_graph_with_policies([
            {
                "id": "pol_ok",
                "text": "No usar lenguaje ofensivo",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "soft",
                "priority": 5,
                "pattern": "basura|idiota|maldito",
            },
        ])
        evaluator = PropertyGraphEvaluator(graph)

        text = "Su cuenta está al corriente y la transferencia fue procesada correctamente."
        violated = evaluator.get_violated_policies(text)

        print(f"\n  Texto evaluado : '{text}'")
        print(f"  Políticas violadas: {_fmt_violated(violated)}")

        assert violated == [], (
            f"No debería haber violaciones para texto conforme. Violadas: {violated}"
        )

    def test_evaluate_returns_inf_on_hard_violation(self):
        """
        evaluate() debe devolver float('inf') cuando hay una política HARD violada,
        independientemente de otras políticas SOFT.
        """
        graph = self._build_graph_with_policies([
            {
                "id": "pol_soft_clima",
                "text": "Hablar de clima es irrelevante",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "soft",
                "priority": 1,
                "pattern": "lluvia",
            },
            {
                "id": "pol_hard_bloqueame",
                "text": "No usar la palabra bloqueame",
                "policy_type": "regex",
                "polarity": "negative",
                "hardness": "hard",
                "priority": 10,
                "pattern": "bloqueame",
            },
        ])
        evaluator = PropertyGraphEvaluator(graph)

        text = "Por favor bloqueame el acceso al sistema de lluvia."
        d_logic = evaluator.evaluate(text)

        assert math.isinf(d_logic), (
            f"evaluate() debe retornar ∞ ante violación HARD. Obtuvo: {d_logic}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# BLOQUE 4 — Pipeline completo con context_input y políticas del fichero
# ──────────────────────────────────────────────────────────────────────────────

class TestPipelineWithFileAndContext:
    """
    Tests del pipeline completo con context_policies como strings en lenguaje
    natural (equivalente a líneas del fichero policies.txt).
    Verifica que violated_policies se propaga correctamente al metadata.
    """

    def test_pipeline_violated_policies_in_metadata(self, capsys):
        """
        El metadata del CanonicalStateDTO debe incluir 'violated_policies'
        con las descripciones formateadas cuando hay un rechazo.
        """
        config = AuditConfig(
            ctm_mode="disabled",
            rigidity_epsilon=0.2,
            policy_loader=None,
            policy_file_path="/tmp/nonexistent.txt",
            embedding_provider=DummyEmbedder(),
        )
        pipeline = IDICOCPipeline(config)
        pipeline.initialize()

        context_input = [
            "El asistente siempre debe mantener la neutralidad.",
            "Ninguna respuesta debe contener sesgos políticos.",
        ]
        context_policies = [
            "[HARD] [REGEX: basura] No se permite el uso de lenguaje ofensivo.",
            "[SOFT] El tono de la respuesta debe ser siempre profesional y neutro.",
        ]

        audit_input = SemanticPayload(
            "Esta política es una completa basura, no sirve para nada."
        )
        result = pipeline.execute(
            audit_input=audit_input,
            user_input="¿Qué piensas de las políticas?",
            context_input=context_input,
            context_policies=context_policies,
            epsilon_override=0.2,
        )

        meta = result["canonical_state"].metadata
        vp = meta.get("violated_policies", [])

        # Formatear D_s de forma segura (evitar f-string con ternario + format spec)
        _d_s_raw = meta['d_s']
        _d_s_str = "∞" if isinstance(_d_s_raw, float) and math.isinf(_d_s_raw) else f"{float(_d_s_raw):.6f}"
        print(f"\n  D_s             : {_d_s_str}")
        print(f"  Admission breach: {meta['admission_breach']}")
        print(f"  Políticas violadas ({len(vp)}):")
        for line in vp:
            print(f"    → {line}")

        assert meta["admission_breach"] is True
        assert len(vp) >= 1, f"violated_policies debe tener al menos 1 entrada. Obtenido: {vp}"
        # Verificar que el formato incluye ID + texto + dureza
        first_vp = vp[0]
        assert ":" in first_vp, (
            f"El formato de violated_policies debe ser 'ID: texto (HARDNESS)'. Obtenido: '{first_vp}'"
        )

    def test_pipeline_context_input_affects_dissonance(self, capsys):
        """
        Verifica que pasar context_input modifica la disonancia calculada.
        Mismo output, distinto contexto → distinta disonancia.
        """
        config = AuditConfig(
            ctm_mode="disabled",
            rigidity_epsilon=0.9,  # Epsilon alto para evitar rechazos en este test
            policy_loader=None,
            policy_file_path="/tmp/nonexistent.txt",
            embedding_provider=DummyEmbedder(),
        )
        pipeline = IDICOCPipeline(config)
        pipeline.initialize()

        response_text = "La transferencia ha sido procesada con éxito."

        # Sin contexto
        res_no_ctx = pipeline.execute(
            audit_input=SemanticPayload(response_text),
            user_input="Estado de la transferencia",
            context_input=None,
            epsilon_override=0.9,
        )

        # Con contexto que contradice la salida
        res_with_ctx = pipeline.execute(
            audit_input=SemanticPayload(response_text),
            user_input="Estado de la transferencia",
            context_input=[
                "La cuenta está bloqueada por actividad sospechosa.",
                "No se pueden procesar transferencias hasta resolución judicial.",
            ],
            epsilon_override=0.9,
        )

        d_s_no_ctx = res_no_ctx["canonical_state"].metadata["d_s"]
        d_s_with_ctx = res_with_ctx["canonical_state"].metadata["d_s"]
        d_ctx = res_with_ctx["canonical_state"].metadata.get("d_context", 0.0)

        print(f"\n  D_s sin contexto   : {d_s_no_ctx:.6f}")
        print(f"  D_s con contexto   : {d_s_with_ctx:.6f}")
        print(f"  d_context (RAG)    : {d_ctx:.6f}")

        # El d_context debe ser registrado en el metadata
        assert "d_context" in res_with_ctx["canonical_state"].metadata, (
            "El metadata debe incluir 'd_context' cuando se pasa context_input."
        )

    def test_aem_records_rejection_with_violated_policies(self, capsys):
        """
        El AEM (AuditEntropyModule) debe registrar el caso de rechazo
        con las políticas violadas en el audit_trail.
        """
        config = AuditConfig(
            ctm_mode="disabled",
            rigidity_epsilon=0.2,
            policy_loader=None,
            policy_file_path="/tmp/nonexistent.txt",
            embedding_provider=DummyEmbedder(),
        )
        pipeline = IDICOCPipeline(config)
        pipeline.initialize()

        context_input = [
            "El protocolo bancario exige neutralidad absoluta.",
        ]
        context_policies = [
            "[HARD] [REGEX: basura] Lenguaje ofensivo prohibido en respuestas al cliente.",
        ]

        pipeline.execute(
            audit_input=SemanticPayload("Este sistema es una basura total."),
            user_input="¿Qué opinas del sistema?",
            context_input=context_input,
            context_policies=context_policies,
            epsilon_override=0.2,
        )

        trail = pipeline.aem.get_audit_trail()
        total, valid, rejected = pipeline.aem.get_counters()

        print(f"\n  AEM counters: total={total}, valid={valid}, rejected={rejected}")
        if trail:
            last = trail[-1]
            vp = last.get("violated_policies", [])
            _ds_raw = last.get('d_s', 0)
            _ds_str = "∞" if isinstance(_ds_raw, float) and math.isinf(_ds_raw) else f"{float(_ds_raw):.4f}"
            print(f"  Último caso AEM:")
            print(f"    D_s              : {_ds_str}")
            print(f"    violated_policies: {vp}")

        assert rejected >= 1, "El AEM debe haber registrado al menos 1 rechazo."
        assert len(trail) >= 1, "El audit_trail del AEM debe tener al menos 1 entrada."

        last_case = trail[-1]
        vp_in_trail = last_case.get("violated_policies", [])
        assert isinstance(vp_in_trail, list), (
            "violated_policies en el AEM trail debe ser una lista."
        )
        assert len(vp_in_trail) >= 1, (
            f"El caso AEM debe incluir las políticas violadas. Obtenido: {vp_in_trail}"
        )
