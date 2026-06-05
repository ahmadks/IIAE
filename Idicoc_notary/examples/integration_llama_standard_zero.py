"""
Ejemplo de Integración: IIAE Standard-Zero con Llama (Phases 1-4)

Este script demuestra:
1. Fase 1 (Cold Loop): Descargar modelos, compilar políticas → W_bank
2. Fase 2 (Interacción): Enviar context_input + user_input
3. Fase 3 (Hot Loop): Generar con contención determinista
4. Fase 4 (Consolidación): Registrar en CTM WAL

Requisitos:
- transformers, torch, sentence-transformers
- Modelos descargados (ejecutar download_models.py --with-llama primero)
- CUDA (recomendado, pero no obligatorio)

Ejecutar:
    python examples/integration_llama_standard_zero.py
"""

import os
import sys
from datetime import datetime, timezone

# Agregar directorio raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient
from idicoc_notary_core.utils.logger import get_logger
from idicoc_notary_core.utils.model_downloader import ensure_llama_downloaded

logger = get_logger("example.integration")


def setup_policies():
    """Crea archivo de ejemplo de políticas."""
    policies_content = """# Políticas de Contención - Ejemplo
# Formato: id | texto | tipo | polaridad | dureza | prioridad | metadata...

P001 | El cliente debe verificar su identidad | rule | affirmative | hard | 10
P002 | No revelar números de cuenta completos | rule | negative | hard | 9
P003 | Limitar transferencias a $50,000 | constraint | affirmative | soft | 5
P004 | Usar lenguaje profesional | style | affirmative | soft | 3
P005 | No hacer promesas de rentabilidad | restriction | negative | hard | 8
"""

    policies_path = "policies.txt"
    with open(policies_path, "w", encoding="utf-8") as f:
        f.write(policies_content)

    print(f"[Setup] Políticas creadas en {policies_path}")
    return policies_path


def phase_1_cold_loop():
    """
    FASE 1: Cold Loop (Inicialización - Compilación)

    Ocurre una sola vez durante boot.
    """
    print("\n" + "=" * 70)
    print("FASE 1: COLD LOOP (Compilación de Políticas)")
    print("=" * 70)

    # Crear archivo de ejemplo
    policies_path = setup_policies()

    # Inicializar configuración (AQUÍ se ejecuta Fase 1)
    print("\n[Fase 1] Asegurando el modelo Llama en cache local...")
    try:
        ensure_llama_downloaded(
            model_name="meta-llama/Meta-Llama-3-8B-Instruct",
            cache_dir="models_cache",
        )
    except Exception as exc:
        print(f"[Fase 1] ⚠ No se pudo descargar Llama automáticamente: {exc}")
        print(
            "  Asegúrate de tener HF_TOKEN configurado o de descargar el modelo manualmente con tests/utils/download_models.py."
        )

    print("\n[Fase 1] Inicializando AuditConfig...")
    config = AuditConfig(
        policy_file_path=policies_path,
        llama_model_name="meta-llama/Meta-Llama-3-8B-Instruct",
        compile_policies_on_init=True,  # ← Activa Cold Loop
        enable_logits_interception=True,  # ← Prepara Hot Loop
        logits_processor_audit_trace=True,  # ← Registra interceptaciones
        instance_name="ai_comercial_example",
    )

    # Resultados de Fase 1
    if config.w_bank:
        print(f"\n[Fase 1] ✓ W_bank compilado con éxito")
        print(f"  - Tokens prohibidos: {len(config.w_bank)}")
        print(f"  - Políticas compiladas: {len(config.invariant_synthesizer.compilation_log)}")

        report = config.invariant_synthesizer.get_compilation_report()
        print(
            f"  - Reporte: success={report['successful']}, "
            f"warnings={report['warnings']}, errors={report['errors']}"
        )
    else:
        print(f"\n[Fase 1] ⚠ W_bank vacío")

    return config


def phase_2_interaction(config: AuditConfig):
    """
    FASE 2: Interacción (Tiempo Real - Context + Instruction)

    Se ejecuta por cada request del usuario.
    """
    print("\n" + "=" * 70)
    print("FASE 2: INTERACCIÓN (Context + Instrucción del Usuario)")
    print("=" * 70)

    # Crear cliente
    client = IDICOCNotaryClient(config)

    # Datos de ejemplo
    context_input = [
        "El cliente tiene 5 años de antigüedad con el banco",
        "Saldo disponible: USD 2,500",
        "Última transacción hace 3 días",
    ]

    user_input = "¿Cuál es el saldo actual de mi cuenta?"

    print(f"\n[Fase 2] Contexto RAG:")
    for i, ctx in enumerate(context_input, 1):
        print(f"  {i}. {ctx}")

    print(f"\n[Fase 2] Instrucción del Usuario:")
    print(f"  {user_input}")

    # Procesar interacción
    print(f"\n[Fase 2] Procesando con wrapper_pipeline...")

    from idicoc_notary_core.audit import SemanticPayload
    result = client.process_interaction(
        audit_input=SemanticPayload(""),  # Vacío en Fase 2
        context_input=context_input,
        context_policies=[],  # Ya compiladas en Fase 1
        user_input=user_input,  # ← NUEVO: instrucción explícita
        epsilon_override=0.0,  # Modo factual
        trace_input="user_session_example_001",
        client_id="client_example_001",
    )

    print(f"\n[Fase 2] ✓ Procesamiento completado")
    print(f"  - Estado canónico generado")
    print(f"  - D_s (disonancia): {result.metadata.get('d_s', 'N/A')}")
    print(f"  - Timestamp: {result.timestamp}")

    return result, context_input, user_input


def phase_3_hot_loop_mock(config: AuditConfig, context_input: list, user_input: str):
    """
    FASE 3: Hot Loop (Generación - Contención Sub-Simbólica)

    Simula generación con Llama + DeterministicMUXLogitsProcessor.
    NOTA: Requiere GPU y modelos descargados. Para demostración sin GPU,
          esta es una ilustración conceptual.
    """
    print("\n" + "=" * 70)
    print("FASE 3: HOT LOOP (Generación con Contención)")
    print("=" * 70)

    if not config.logits_processor:
        print(f"\n[Fase 3] ⚠ Procesador de logits no inicializado")
        print(f"          (Requiere --with-llama en download_models.py)")
        return None

    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM

        print(f"\n[Fase 3] Cargando Llama tokenizador...")
        tokenizer = AutoTokenizer.from_pretrained(
            config.llama_model_name,
            cache_dir="models_cache",
        )

        # Construir prompt
        system_prompt = "\n".join(context_input)
        full_prompt = f"System: {system_prompt}\n\nUser: {user_input}\n\nAssistant:"

        print(f"\n[Fase 3] Prompt construido:")
        print(f"  Longitud: {len(full_prompt)} caracteres")

        print(f"\n[Fase 3] Tokenizando...")
        input_ids = tokenizer.encode(full_prompt, return_tensors="pt")
        print(f"  Tokens: {input_ids.shape[1]} (en CPU)")

        print(f"\n[Fase 3] Generando con contención W_bank...")
        print(f"  - W_bank size: {len(config.w_bank)} tokens prohibidos")
        print(f"  - Procesador: DeterministicMUXLogitsProcessor (O(1))")

        # NOTA: Esto requiere GPU y modelo descargado
        # Acá sería:
        # model = AutoModelForCausalLM.from_pretrained(...)
        # outputs = model.generate(
        #     input_ids,
        #     logits_processor=config.logits_processor,
        #     max_new_tokens=200,
        #     temperature=0.0,  # Determinístico
        # )
        # output_text = tokenizer.decode(outputs[0])

        print(f"\n[Fase 3] Ejemplo de output esperado:")
        print(f"  'Su saldo actual es USD 2,500'")
        print(f"  (No contiene números de cuenta completos, cumple P002)")

        # Log de auditoría
        if config.logits_processor.audit_trace:
            print(f"\n[Fase 3] Auditoría de Logits:")
            print(f"  - Iteraciones: 15 (ejemplo)")
            print(f"  - Tokens bloqueados promedio: 342 por iteración")
            print(f"  - Latencia agregada: <5ms (GPU)")

        output_text = "Su saldo actual es USD 2,500"

        return output_text

    except ImportError:
        print(f"\n[Fase 3] ⚠ Transformers no disponible (simulación)")
        output_text = "Su saldo actual es USD 2,500"
        return output_text
    except Exception as e:
        print(f"\n[Fase 3] ❌ Error: {e}")
        return None


def phase_4_consolidation(config: AuditConfig, user_input: str, output_text: str):
    """
    FASE 4: Consolidación (Trazabilidad - CTM WAL)

    Registra generación en ledger criptográfico.
    """
    print("\n" + "=" * 70)
    print("FASE 4: CONSOLIDACIÓN (Trazabilidad CTM WAL)")
    print("=" * 70)

    try:
        from idicoc_notary_core.audit.ctm_client import CTMClient
        import hashlib

        print(f"\n[Fase 4] Inicializando CTM...")
        ctm = CTMClient(config)

        # Calcular hashes
        user_input_hash = hashlib.sha256(user_input.encode()).hexdigest()[:16]
        output_hash = hashlib.sha256(output_text.encode()).hexdigest()[:16]

        print(f"\n[Fase 4] Registrando en WAL:")
        print(f"  - user_input_hash: {user_input_hash}...")
        print(f"  - output_hash: {output_hash}...")
        print(f"  - timestamp: {datetime.now(timezone.utc).isoformat()}")
        print(f"  - client_id: client_example_001")

        # Registrar (si CTM está disponible)
        try:
            result = ctm.notarize(
                input_hash=user_input_hash,
                output_hash=output_hash,
                metadata={
                    "phase": "3-hot-loop",
                    "output_text": output_text,
                    "client_id": "client_example_001",
                },
            )
            print(f"\n[Fase 4] ✓ Registrado exitosamente")
            print(f"  - Merkle path: {result.get('merkle_path', 'N/A')[:40]}...")
        except Exception as e:
            print(f"\n[Fase 4] ⚠ CTM no disponible ({e})")
            print(f"         Simulación: registro local completado")

    except Exception as e:
        print(f"\n[Fase 4] ⚠ Error en consolidación: {e}")


def main():
    """Ejecuta todas las fases."""
    print("\n" + "=" * 70)
    print("IIAE STANDARD-ZERO - EJEMPLO INTEGRACIÓN COMPLETO")
    print("=" * 70)
    print(f"\nTiempo: {datetime.now(timezone.utc).isoformat()}")

    try:
        # Fase 1: Cold Loop (Compilación)
        config = phase_1_cold_loop()

        # Fase 2: Interacción (Context + Instrucción)
        result, context_input, user_input = phase_2_interaction(config)

        # Fase 3: Hot Loop (Generación con Contención)
        output_text = phase_3_hot_loop_mock(config, context_input, user_input)

        # Fase 4: Consolidación (Trazabilidad)
        if output_text:
            phase_4_consolidation(config, user_input, output_text)

        print("\n" + "=" * 70)
        print("✓ EJEMPLO COMPLETADO CON ÉXITO")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
