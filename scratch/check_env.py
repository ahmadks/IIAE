try:
    import torch
    import torchvision
    from sentence_transformers import SentenceTransformer
    print(f"Torch version: {torch.__version__}")
    print(f"Torchvision version: {torchvision.__version__}")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    print("SUCCESS: Semantic model loaded correctly.")
except Exception as e:
    print(f"FAILURE: {e}")
