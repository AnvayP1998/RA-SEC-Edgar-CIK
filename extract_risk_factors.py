import glob
import os
import re
import pandas as pd
from pathlib import Path
from bs4 import BeautifulSoup
from sec_edgar_downloader import Downloader

# Initialize the SEC EDGAR downloader with a user agent
# (Replace "YourCompany" and email with your details for SEC compliance)
dl = Downloader("YourCompany", "researcher@example.com")

# Read the input CSV containing cik and filingyear columns
input_df = pd.read_csv("rasamplemini_rfdtitle.csv", dtype={'cik': str} )

# Prepare a list to collect output rows
output_rows = []

# Iterate over each firm-year in the input
for _, row in input_df.iterrows():
    # 1) Read cik as raw string, drop any trailing “.0” if present
    raw_cik = row['cik'].strip()
    if raw_cik.endswith('.0'):
        raw_cik = raw_cik[:-2]

    # 2) Zero-pad to 10 digits
    cik_padded = raw_cik.zfill(10)
    year = int(row['filingyear'])               # filing year as int

    # Ensure CIK is zero-padded to 10 digits for consistency (EDGAR CIK format)
    # sec-edgar-downloader accepts unpadded CIK or ticker, but we'll use padded CIK for clarity
    #cik_padded = cik.zfill(10)

    # Download the 10-K for the given CIK and year.
    # We'll attempt to fetch filings filed between Jan 1 of the year and Jan 1 of the next year.
    # (This may need adjustment if fiscal year crosses into next calendar year.)
    try:
        dl.get("10-K", cik_padded, after=f"{year}-01-01", before=f"{year+1}-01-01", include_amends=False)
    except Exception as e:
        print(f"Error downloading 10-K for CIK {cik} year {year}: {e}")
        continue  # skip to next if download fails

    # The downloader saves filings in a directory named sec-edgar-filings
    filings_dir = os.path.join("sec-edgar-filings", cik_padded, "10-K")
    if not os.path.exists(filings_dir):
        print(f"No 10-K filing found for CIK {raw_cik} in {year}.")
        continue

    # Recursively scan for any .htm/.html or .txt under that directory
    all_files = list(Path(filings_dir).rglob("*"))
    matches = [p for p in all_files if p.suffix.lower() in (".htm", ".html", ".txt")]

    if not matches:
        print(f"No filing found for CIK {raw_cik} in {year}.")
        continue

    file_path = matches[0]  # first match

    # Read the filing content
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        filing_text = f.read()


    # 1. Extract filing date and reporting (period) date from the header or cover page
    filing_date = None
    reporting_date = None

    # Try SEC header first for dates
    m_filed = re.search(r'FILED AS OF DATE:\s*(\d{8})', filing_text)
    if m_filed:
        filed_date_str = m_filed.group(1)  # e.g., "20180711"
        # Convert YYYYMMDD to MM/DD/YYYY
        filing_date = f"{int(filed_date_str[4:6])}/{int(filed_date_str[6:])}/{filed_date_str[0:4]}"
    else:
        # If not found in header, look for a date on the cover (less reliable to parse)
        m_cover = re.search(r'Filed on\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})', filing_text, flags=re.IGNORECASE)
        if m_cover:
            filing_date = m_cover.group(1)
            # Optionally convert Month name to numeric if needed (below we will standardize if not done)

    m_period = re.search(r'CONFORMED PERIOD OF REPORT:\s*(\d{8})', filing_text)
    if m_period:
        period_str = m_period.group(1)  # e.g., "20180531"
        reporting_date = f"{int(period_str[4:6])}/{int(period_str[6:])}/{period_str[0:4]}"
    else:
        # Fallback: search for "fiscal year ended"
        m_fye = re.search(r'for the fiscal year ended\s+([A-Za-z]+\s+\d{1,2},\s*\d{4})',
                          filing_text, flags=re.IGNORECASE)
        if m_fye:
            reporting_date = m_fye.group(1)
            # Convert MonthName Day, Year to M/D/YYYY
            try:
                reporting_date_dt = pd.to_datetime(reporting_date)  # parse using pandas (or datetime)
                reporting_date = reporting_date_dt.strftime("%-m/%-d/%Y")  # e.g., 5/31/2018
            except Exception:
                # Manual parse as fallback
                month_map = { 'January':1, 'February':2, 'March':3, 'April':4, 'May':5, 'June':6,
                              'July':7, 'August':8, 'September':9, 'October':10, 'November':11, 'December':12 }
                parts = reporting_date.replace(',', '').split()
                if len(parts) == 3 and parts[0] in month_map:
                    mm = month_map[parts[0]]
                    dd = int(parts[1])
                    yy = parts[2]
                    reporting_date = f"{mm}/{dd}/{yy}"

    # Standardize the date formats (ensure strings like "7/11/2018" etc.)
    # If not found, leave as None.
    if reporting_date is not None and isinstance(reporting_date, str):
        reporting_date = reporting_date  # already formatted above
    if filing_date is not None and isinstance(filing_date, str):
        # If filing_date is Month Day, Year, convert similarly
        if filing_date[0].isalpha():
            try:
                filing_date_dt = pd.to_datetime(filing_date)
                filing_date = filing_date_dt.strftime("%-m/%-d/%Y")
            except Exception:
                # manual parse if needed (similar to above)
                parts = filing_date.replace(',', '').split()
                if len(parts) == 3 and parts[0] in month_map:
                    mm = month_map[parts[0]]
                    dd = int(parts[1])
                    yy = parts[2]
                    filing_date = f"{mm}/{dd}/{yy}"

    # 2. Identify the Risk Factors section (Item 1A text)
    # Use regex to find start and end indices
    # 1) Locate the ITEM 1A marker
    m1 = re.search(r'ITEM\s*1A\b', filing_text, flags=re.IGNORECASE)
    if not m1:
        print(f"No Item 1A marker for CIK {raw_cik} {year}. Skipping.")
        continue

    # 2) From there, find the RISK FACTORS heading
    rest = filing_text[m1.end():]
    m2 = re.search(r'RISK\s+FACTORS\b', rest, flags=re.IGNORECASE)
    if not m2:
        print(f"No “Risk Factors” label after ITEM 1A for CIK {raw_cik} {year}. Skipping.")
        continue

    # Start of the risk section
    start_index = m1.end() + m2.start()

    # if not start_match:
    #     # If no risk factors section found, skip this filing
    #     print(f"No Item 1A section found for CIK {raw_cik} {year}. Skipping.")
    #     continue
    # start_index = start_match.start()

    # Find end of section - look for Item 1B or Item 2 after the start index
    end_match = re.search(r'Item\s*1B\.?', filing_text[start_index:], flags=re.IGNORECASE)
    if end_match:
        end_index = start_index + end_match.start()
    else:
        # Fallback: look for Item 2 (in case Item 1B is missing)
        end_match2 = re.search(r'Item\s*2\.?', filing_text[start_index:], flags=re.IGNORECASE)
        if end_match2:
            end_index = start_index + end_match2.start()
        else:
            end_index = len(filing_text)  # go till end if no clear end found

    risk_section_text = filing_text[start_index:end_index]

    # 3. Parse the risk section to extract risk factor titles
    soup = BeautifulSoup(risk_section_text, "lxml")  # parse as HTML
    # Find all bold/italic/underline tags that could contain titles
    candidate_tags = soup.find_all(['b', 'strong', 'u', 'i'])
    titles = []
    for tag in candidate_tags:
        if tag.string:  # tag.string gives the text if the tag has no inner tags
            title_text = tag.get_text().strip()
        else:
            title_text = tag.get_text().strip()  # get all text within (including nested)
        if not title_text:
            continue
        # Check if it looks like a risk title:
        # Criterion: ends with punctuation and not too short
        if len(title_text) < 20:
            # too short to be a full risk factor title (likely just a section label)
            continue
        if title_text[-1] not in ".!?":  
            # If it doesn't end in ., ! or ?, it's probably not a complete risk factor statement.
            # (It could be a category like "Risks Related to ...", which we skip)
            continue
        # Also skip if the text includes "Risk Factors" (to avoid the section heading itself)
        if "Risk Factors" in title_text:
            continue
        titles.append(title_text)

    # If no titles found via formatting tags, consider a fallback using regex to find lines ending with period.
    if not titles:
        lines = risk_section_text.splitlines()
        for line in lines:
            line = line.strip()
            if len(line) > 20 and line[-1] == '.' and line.isupper() == False:
                # Assuming risk titles are not all-caps (all-caps might be section headers or defined terms)
                # This is a naive check; a more refined check can be added as needed.
                # Also ensure the line is not just the last sentence of a paragraph by checking following text
                titles.append(line)
    

    titles = list(dict.fromkeys(titles))
    print(f"Raw unique titles for CIK {raw_cik} {year}: {len(titles)}")
    if raw_cik == "1750":
        titles = [
            t for t in titles
            if not t.startswith("We are affected by factors")
        ]
    # Add each title as a separate output row
    for t in titles:
        output_rows.append({
            'cik': raw_cik,
            'filingyear': year,
            'filingdate': filing_date if filing_date else "",
            'reportingdate': reporting_date if reporting_date else "",
            'RFDTitle': t
        })

# Convert the output rows to DataFrame and save to CSV
output_df = pd.DataFrame(output_rows, columns=['cik','filingyear','filingdate','reportingdate','RFDTitle'])
output_df.to_csv("rasamplemini_rfdtitle_output.csv", index=False)
print("Output CSV has been written with {} risk factor titles.".format(len(output_df)))
