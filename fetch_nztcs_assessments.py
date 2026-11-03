#!/usr/bin/env python3
import csv
from datetime import datetime
from html.parser import HTMLParser

import requests


# Strip HTML tags (mainly <i> for italics)
class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.text = []

    def handle_data(self, d):
        self.text.append(d)

    def get_data(self):
        return ''.join(self.text)

def strip_html(text):
    if not text:
        return text
    stripper = HTMLStripper()
    stripper.feed(text)
    return stripper.get_data()

def fetch_assessments(report_id, page_size=1000):
    """Fetch all assessments for a report from NZTCS API"""
    url = "https://nztcs.org.nz/rest/assessmentSearch"
    payload = {
        "reportId": report_id,
        "pageNumber": 1,
        "pageSize": page_size,
        "showArchived": True
    }

    print(f"Fetching assessments for report {report_id}...", flush=True)
    response = requests.post(url, json=payload)
    response.raise_for_status()

    data = response.json()
    total = data.get('total', 0)
    results = data.get('searchResults', [])

    print(f"Retrieved {len(results)} of {total} assessments", flush=True)
    return results

def save_csv(assessments, filename):
    """Save assessments to CSV with selected fields for Wikipedia speciesbox"""
    if not assessments:
        print("No assessments to save")
        return

    # Fields relevant for Wikipedia speciesbox updates
    fields = [
        'speciesId',
        'assessmentId',
        'nztcsSpeciesName',
        'commonName',
        'conservationStatusTitle',
        'categoryTitle',
        'criteriaTitle',
        'qualifiers',
        'reportName',
        'reportYear',
        'popSizeTitle',
        'popTrendTitle'
    ]

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for assessment in assessments:
            row = {field: assessment.get(field, '') for field in fields}
            # Strip HTML from scientific and common names
            row['nztcsSpeciesName'] = strip_html(row['nztcsSpeciesName'])
            row['commonName'] = strip_html(row['commonName'])
            writer.writerow(row)

    print(f"Saved to {filename}")

if __name__ == "__main__":
    import sys

    # Default to report 1176 (Lepidoptera 2025), but allow override
    report_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1176

    assessments = fetch_assessments(report_id)
    filename = f"nztcs_report_{report_id}_{datetime.now().strftime('%Y%m%d')}.csv"
    save_csv(assessments, filename)
