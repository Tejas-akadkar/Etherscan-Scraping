# Etherscan-Scraping
Etherscan labelcloud scraper. Scrapes accounts and tokens data from Etherscan. It uses hybrid approach of multithreading along with selenium/chrome to scrape data faster and disables the loading of images so it wont ent up consuming all the bandwidth.It creates 3 files and 1 directory: <br>
1. scraped_labels.txt
2. scraped_accounts.txt
3. scraped_tokens.txt
<br>And the directory is "CSVs" which contains all scraped data, each label may have 2 CSVs:
1. label_account.csv
2. label_tokens.csv

