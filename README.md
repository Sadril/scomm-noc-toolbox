# SComm NOC Toolbox

A Streamlit-based toolbox for NOC engineers. All tools share one URL
and one virtual environment.

## Tools

| # | Tool | Purpose |
|---|---|---|
| 🔎 | DWDM Lookup | Search DWDM links by path, node, or OCR snapshot |
| 📨 | Pending TT Scraper | Fetch pending TT IDs for HTD / Huawei / Contains |
| 🔍 | TT Finder | Find any TT ID by keyword + status |
| 📞 | RIO Lookup | Look up SC head, RIO successor, RIO HOD contacts |
| 📝 | Alarm Formatter | Format alarm reports + copy comment library |
| 📨 | Pending Task (STL + Info-Sarkar-Ph3) | Fetch pending tickets per company/client |

## Screenshots

![img.png](img.png)<add a few screenshots here once available>

## Requirements

- Python 3.10+
- Tesseract OCR (only needed for the "By Snapshot" tab)

## Setup

```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
