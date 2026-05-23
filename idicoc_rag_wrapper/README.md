# idicoc_rag_wrapper

Adaptador ligero entre IA comercial, RAG y el núcleo determinista `idicoc_core`.

Este paquete solo contiene:
- configuración separada en `config.py`
- contratos y tipos en `base.py`
- excepciones específicas en `exceptions.py`
- adaptación de entrada y medición de D_s en `wrapper_pipeline.py`

No incluye lógica de modelos ni de recuperación semántica.
