# citation-report
Selenium-based Python script creating author citation reports from Web of Science.
Results are processed using LaTeX and BibTeX.

## Requires
- working Chrome Browser
- working LaTeX and BibTeX
- ChromeDriver (https://sites.google.com/a/chromium.org/chromedriver)
	Should be added to PATH or to the script folder.
- Python bibtexparser (https://bibtexparser.readthedocs.org/en/v0.6.2/install.html)
- Python Selenium (http://selenium-python.readthedocs.org/installation.html)

## Usage
Call search function with the following inputs:
    Web of Science query (e.g. AU=Last,F* for an author search)
    name of the PDF file to be generated
    new (boolean) - force new databse fetch, or use old data if exists
    full (boolean) - list all citing papers or just the counts for each paper
See example at the end of wos.py file.

BibTex data might not be available for some papers. These will be listed at the
end of the PDF file.
