"""
Sube contalink.py a backend/routes/contalink.py en taxnfin/TAXNFIN1
Ejecutar en PowerShell:  python upload_contalink.py
"""
import base64, json, os
import urllib.request, urllib.error

REPO    = "taxnfin/TAXNFIN1"
PATH    = "backend/routes/contalink.py"
BRANCH  = "main"
API     = f"https://api.github.com/repos/{REPO}/contents/{PATH}"

def main():
    token = input("GitHub token: ").strip()
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }

    # Leer el archivo local
    script_dir = os.path.dirname(os.path.abspath(__file__))
    local_file = os.path.join(script_dir, "contalink__8_.py")
    if not os.path.exists(local_file):
        # Intentar con nombre limpio también
        local_file = os.path.join(script_dir, "contalink.py")
    
    with open(local_file, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    # Obtener SHA actual (si el archivo ya existe)
    sha = None
    req = urllib.request.Request(API, headers=headers)
    try:
        with urllib.request.urlopen(req) as r:
            data = json.loads(r.read())
            sha = data.get("sha")
            print(f"✅ Archivo existente encontrado — SHA: {sha[:7]}...")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("📄 Archivo nuevo — se creará.")
        else:
            print(f"❌ Error al obtener SHA: {e.code} {e.reason}")
            return

    # Armar payload
    payload = {
        "message": "feat: update contalink.py with search-accounts and probe-endpoints",
        "content": content_b64,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    # PUT
    req2 = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req2) as r:
            result = json.loads(r.read())
            action = "actualizado" if sha else "creado"
            commit = result.get("commit", {}).get("sha", "")[:7]
            print(f"✅ contalink.py {action} exitosamente — commit: {commit}")
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ Error al subir: {e.code} {e.reason}")
        print(body[:300])

if __name__ == "__main__":
    main()
