#!/bin/bash
# FloMind Budget Dashboard — Lanceur macOS / Linux

set -e
cd "$(dirname "$0")"

echo ""
echo "  ╔═══════════════════════════════════════════════════════╗"
echo "  ║         F L O M I N D   Budget Dashboard              ║"
echo "  ║         CDG x Data x IA pour PME  —  v1.0            ║"
echo "  ╚═══════════════════════════════════════════════════════╝"
echo ""

# [1/5] Python
echo "  [1/5] Vérification Python..."
if ! command -v python3 &>/dev/null; then
    echo "  [ERREUR] Python 3 non trouvé. Installer Python 3.11+"
    exit 1
fi
echo "         $(python3 --version) ✓"

# [2/5] Venv
echo "  [2/5] Environnement virtuel..."
if [ ! -d ".venv" ]; then
    echo "         Création du venv..."
    python3 -m venv .venv
fi
source .venv/bin/activate
echo "         Venv activé ✓"

# [3/5] Dépendances
echo "  [3/5] Dépendances..."
if ! python -c "import streamlit" &>/dev/null; then
    echo "         Installation en cours..."
    pip install -r requirements.txt --quiet
fi
echo "         Dépendances OK ✓"

# [4/5] Données
echo "  [4/5] Données de démonstration..."
if [ ! -f "data/sample_budget_v2.xlsx" ]; then
    echo "         Génération des données..."
    python generators/generate_sample_v3.py > /dev/null
fi
echo "         Données OK ✓"

# [5/5] Lancement
PORT=8501
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then PORT=8502; fi

echo ""
echo "  Dashboard → http://localhost:$PORT"
echo "  Ctrl+C pour arrêter"
echo ""

# Ouvrir le navigateur
sleep 2 && (open "http://localhost:$PORT" 2>/dev/null || xdg-open "http://localhost:$PORT" 2>/dev/null) &

streamlit run app.py \
    --server.port=$PORT \
    --server.headless=true \
    --server.fileWatcherType=none \
    --browser.gatherUsageStats=false
