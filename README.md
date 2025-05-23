# SEC EDGAR 10-K Risk Factor Extractor

This Python script downloads 10-K filings from the SEC EDGAR archive for a sample of firms, locates the “Item 1A – Risk Factors” section in each filing, and extracts the individual risk-factor titles into a CSV. It handles de-duplication and a few edge cases (e.g. firms with no Item 1A, small formatting quirks).

---

## 📁 Repository Structure

.
├── extract_risk_factors.py # Main extraction script
├── rasamplemini_rfdtitle.csv # Input: sample CIKs & filing years
├── rasamplemini_rfdtitle_output.csv # Output: your extracted titles
├── README.md # This file
└── venv/ # (optional) Python virtualenv

---

## 🚀 Quick Start

### 1. Clone & create a venv

```bash
git clone <your-repo-url>
cd <your-repo-dir>
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows PowerShell
```

### 2. Install dependencies

```bash
pip install pandas bs4 sec-edgar-downloader
```

### 3. Prepare your input

rasamplemini_rfdtitle.csv must have columns:

- cik (str) — SEC CIK (no trailing “.0”)
- filingyear (int) — calendar year to search for 10-K

### 4. Run the extractor

```bash
python extract_risk_factors.py
```

After it finishes, you’ll see logs like:

```
Raw unique titles for CIK 1750 2018: 19
… 
Final unique titles for CIK 1750 2018: 18
…
Output CSV has been written with 342 risk factor titles.
```

### 5. Review the output

rasamplemini_rfdtitle_output.csv with columns:

- cik — firm CIK
- filingyear
- filingdate — Date filed (MM/DD/YYYY)
- reportingdate — Fiscal period end (MM/DD/YYYY)
- RFDTitle — Extracted risk-factor title

---

🔧 How It Works

- Download each firm-year’s 10-K using sec_edgar_downloader.
- Scan the downloaded folder for any .htm, .html, or .txt.
- Locate the Item 1A marker (case-insensitive), then the “Risk Factors” heading.
- Crop between that start and the next Item 1B (or Item 2) marker.
- Parse the snippet with BeautifulSoup, finding all <b>, <strong>, <u>, <i> tags (common title formatting).
- Filter:
  - Minimum length, ends in . ! ?, no “Risk Factors” header itself.
  - Fallback: any long line ending in “.”.
- Dedupe and (for CIK 1750 only) drop one extra boilerplate title.
- Write each clean title to the output CSV.

---

⚙️ Customization & Tips

- Date windows  
  By default, we fetch filings with after=YEAR-01-01 and before=YEAR+1-01-01. Adjust if a firm’s fiscal year spans two calendar years.

- Additional filters  
  You can tweak the title-extraction heuristics inside the titles = … loop to catch other formatting patterns.

- Email/User-Agent  
  Replace the dummy "YourCompany", "researcher@example.com" in Downloader(...) with your own so you comply with SEC fair-use policies.

- Skipping  
  If a firm didn’t file a 10-K or if the script can’t find an Item 1A marker, it will print a “Skipping” message and move on. That’s expected for some CIKs.

---

🐞 Troubleshooting

- Permission errors on sec-edgar-filings/…  
  Ensure your script runs with read/write access in your working directory.

- No .htm files found  
  Check that sec_edgar_downloader actually downloaded.  
  You can browse sec-edgar-filings/<CIK>/10-K/<accession>/full-submission.txt manually.

- Wrong counts  
  Add temporary print(len(titles), titles[:3]) to inspect what your heuristics are catching.

---

📄 License & Citation

Feel free to reuse and adapt. If you build upon this in published research, please cite the original assignment and Gaulin (2019). Enjoy!
