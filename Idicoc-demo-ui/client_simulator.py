import sys
import os
import time
import argparse
import random
import string
import numpy as np

# Asegurar que el core esté en el path de Python
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Idicoc_notary"))
)

from idicoc_notary_core import IDICOCNotaryClient
import IdicocConfg

def load_policies_from_file(file_path: str) -> list[dict]:
    policies = []
    if not os.path.exists(file_path):
        return policies
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("|")
            if len(parts) >= 6:
                policies.append(
                    {
                        "id": parts[0],
                        "text": parts[1],
                        "policy_type": parts[2],
                        "polarity": parts[3],
                        "hardness": parts[4],
                        "priority": int(parts[5]),
                        "source_text": parts[1],
                    }
                )
    return policies

def introduce_typo_noise(text: str, rate: float) -> str:
    if not text or rate <= 0.0:
        return text
    chars = list(text)
    typo_count = max(1, int(len(chars) * rate))
    for _ in range(typo_count):
        if not chars:
            break
        idx = random.randrange(len(chars))
        op = random.choice(["swap", "replace", "delete", "insert"])
        if op == "swap" and idx < len(chars) - 1:
            chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
        elif op == "replace":
            chars[idx] = random.choice(string.ascii_lowercase)
        elif op == "delete" and len(chars) > 1:
            chars.pop(idx)
        elif op == "insert":
            chars.insert(idx, random.choice(string.ascii_lowercase))
    return "".join(chars)

def main():
    parser = argparse.ArgumentParser(description="IIAE Notary Headless Client Simulator")
    parser.add_argument("--mode", choices=["Numerico", "Semantico"], default="Numerico")
    parser.add_argument("--epsilon", type=float, default=0.20)
    parser.add_argument("--noise", type=float, default=0.05, help="Sigma para ruido numérico, o tasa de error para texto")
    parser.add_argument("--interval", type=float, default=1.0, help="Intervalo en segundos entre señales")
    parser.add_argument("--text", type=str, default="Transfer 50000.00 euros within limits.", help="Texto base para modo Semántico")
    
    args = parser.parse_args()

    # Cargar politicas
    policies_file = os.path.join(os.path.dirname(__file__), "policies.txt")
    static_policies = load_policies_from_file(policies_file)
    
    if args.mode == "Semantico":
        policies = static_policies
    else:
        policies = [ax for ax in static_policies if ax["id"].startswith("ax_num")]

    print(f"[*] Inicializando IDICOC Notary en modo {args.mode} (Epsilon={args.epsilon})...")
    config = IdicocConfg.build_notary_config(args.epsilon, policies)
    client = IDICOCNotaryClient(config)
    
    print("[*] Iniciando inyección de señales (Ctrl+C para detener)")
    try:
        while True:
            if args.mode == "Numerico":
                base_k = np.array([0.25, 0.25, 0.25, 0.25])
                noise = np.random.normal(0, args.noise, 4) if args.noise > 0 else np.zeros(4)
                perturbed = base_k + noise
                perturbed = np.clip(perturbed, 1e-12, 1.0)
                perturbed /= perturbed.sum()
                audit_input = perturbed.tolist()
                print(f"[>] Enviando señal numérica: {[round(v, 4) for v in audit_input]}")
            else:
                audit_input = introduce_typo_noise(args.text, args.noise)
                print(f"[>] Enviando texto semántico: '{audit_input}'")
            
            result = client.process_interaction(
                audit_input=audit_input,
                epsilon_override=args.epsilon,
                trace_input="client_simulator_headless",
                client_id="simulated_client"
            )
            
            D_s = result.metadata.get("d_s", 0.0)
            correction = result.metadata.get("correction_flag", False)
            admitted = result.metadata.get("admission_metrics", {}).get("admitted", False)
            
            if admitted:
                status = "\033[92mADMITIDA\033[0m" if not correction else "\033[93mCORREGIDA\033[0m"
            else:
                status = "\033[91mRECHAZADA\033[0m"
                
            print(f"[<] Notario Responde: {status} | D_s: {D_s:.4f} | Epsilon: {args.epsilon}")
            print("-" * 60)
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n[*] Simulación detenida.")

if __name__ == "__main__":
    main()
