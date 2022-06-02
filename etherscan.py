import csv
import json
import os
import random
import threading
import time
import traceback

import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

API_KEY = "05b802522dd0ce9f6cd24b443db4d88a"
data_sitekey = '6Le1YycTAAAAAJXqwosyiATvJ6Gs2NLn8VEzTVlS'
es = "etherscan.io"
page_url = f'https://{es}/login'
timeout = 10
debug = False
# blocked = ["liqui.io", "remittance+"]
account_headers = ['Address', 'Name Tag', 'Name Tag URL', 'AddressLink', 'AddressType', 'LabelIDs',
                   'Subcategory', 'Time']
token_headers = ['Address', 'AddressLink', 'Name', 'Abbreviation', 'Website', 'SocialLinks', 'Image', 'LabelIDs',
                 'OverviewText', 'MarketCap', 'Holder', 'AdditionalInfo', 'Overview', 'AddressType', 'Time']
semaphore = threading.Semaphore(10)
lock = threading.Lock()
busy = False
scraped = {}


def getToken(soup, tr):
    tkn = tr['Contract Address']
    try:
        try:
            tr['Description'] = json.loads(soup.find('script', {"type": "application/ld+json"}).text)['description']
        except:
            tr['Description'] = ""
        hldr = 'ContentPlaceHolder1_tr_tokenHolders'
        try:
            print(soup.find('div', {'class': 'table-responsive mb-2'}).text)
        except:
            pass
        data = {
            "Address": tkn,
            "AddressLink": f"https://{es}/address/{tkn}",
            "Name": soup.find('div', {'class': "media-body"}).find('span').text.strip(),
            "Abbreviation": getTag(soup, 'div', {'class': 'col-md-8 font-weight-medium'}).split()[-1],
            "Website": soup.find('div', {"id": 'ContentPlaceHolder1_tr_officialsite_1'}).find('a')['href'],
            "SocialLinks": [{li.find('a')['data-original-title'].split(':')[0]: li.find('a')['href']} for li in
                            soup.find_all('li', {"class": "list-inline-item mr-3"})],
            "Image": f"https://{es}/{soup.find('img', {'class': 'u-sm-avatar mr-2'})['src']}",
            "LabelIDs": [a.text for a in soup.find_all('div', {'class': 'mt-1'})[1].find_all('a') if
                         soup.find_all('div', {'class': 'mt-1'}) is not None and len(
                             soup.find_all('div', {'class': 'mt-1'})) > 1],
            "OverviewText": soup.find('h2', {"class": "card-header-title"}).find('span').text.strip()[1:-1],
            "MarketCap": tr['Market Cap'],
            "Holder": soup.find('div', {'id': hldr}).find('div', {'class': 'mr-3'}).text.split('(')[0].strip(),
            "AdditionalInfo": "",
            "Overview": tr['Description'],
            "AddressType": tr['Subcategory'],
            "Time": time.strftime('%d-%m-%Y %H:%M:%S'),
        }
        print(json.dumps(data, indent=4))
        filename = f"./CSVs/{tr['Label']}-token.csv"
        if not os.path.exists(filename):
            with open(filename, 'w', newline='', encoding='utf8') as file:
                csv.DictWriter(file, fieldnames=token_headers).writeheader()
        with open(filename, 'a', newline='', encoding='utf8') as file:
            csv.DictWriter(file, fieldnames=token_headers).writerow(data)
        with open('scraped_tokens.txt', 'a') as sfile:
            sfile.write(tkn + "\n")
        scraped['tokens'].append(tkn)
    except:
        traceback.print_exc()
        with open('Error-Token.txt', 'a') as efile:
            efile.write(f"{tkn}\n")


def getAccount(soup, tr):
    addr = tr['Address']
    try:
        try:
            print(soup.find('div', {'class': 'table-responsive mb-2'}).text.replace('OVERVIEW', ''))
        except:
            pass
        tag = soup.find("span", {"title": 'Public Name Tag (viewable by anyone)'})
        data = {
            "Name Tag": tag.text if tag is not None else tr['Name Tag'],
            "Address": addr,
            "AddressLink": f"https://{es}/address/{addr}",
            "AddressType": soup.find('h1').text.strip().split()[0],
            "Name Tag URL": tag.parent.find('a')[
                'href'] if tag is not None and tag.parent is not None and tag.parent.find('a') is not None else "",
            "LabelIDs": [a.text for a in soup.find_all('div', {'class': 'mt-1'})[1].find_all('a') if
                         soup.find_all('div', {'class': 'mt-1'}) is not None and len(
                             soup.find_all('div', {'class': 'mt-1'})) > 1],
            "Subcategory": tr['Subcategory'],
            "Time": time.strftime('%d-%m-%Y %H:%M:%S'),
        }
        print(json.dumps(data, indent=4))
        filename = f"./CSVs/{tr['Label']}-accounts.csv"
        if not os.path.exists(filename):
            with open(filename, 'w', newline='', encoding='utf8') as file:
                csv.DictWriter(file, fieldnames=account_headers).writeheader()
        with open(filename, 'a', newline='', encoding='utf8') as file:
            csv.DictWriter(file, fieldnames=account_headers).writerow(data)
        with open('scraped_accounts.txt', 'a') as sfile:
            sfile.write(addr + "\n")
        scraped['accounts'].append(addr)
    except:
        traceback.print_exc()
        with open('Error-Account.txt', 'a') as efile:
            efile.write(f"{addr}\n")
        # print(soup)


def scrape(driver, tr, at):
    global busy
    while busy:
        time.sleep(1)
    addr = tr['Address'] if at == 'accounts' else tr['Contract Address']
    url = f'https://{es}/{"address" if at == "accounts" else "token"}/{addr}'
    with semaphore:
        print(f"Working on {at[:-1]} {addr} {url}")
        soup = getSession(driver, url)
    if busy:
        while busy:
            time.sleep(random.randint(1, 5))
        with semaphore:
            print(f"Working on {at[:-1]} {addr}")
            soup = getSession(driver, url)
    if "Maintenance Mode" in soup.find('title').text:
        busy = True
        print(soup.find('title').text.strip())
        with lock:
            driver.get(url)
            soup = getSoup(driver)
            while "Maintenance Mode" in soup.find('title').text:
                print(soup.find('title').text.strip())
                busy = True
                driver.get(url)
                time.sleep(random.randint(3, 5))
                soup = getSoup(driver)
    busy = False
    if at == "tokens":
        getToken(soup, tr)
    else:
        getAccount(soup, tr)


def scrapeLabel(driver, label, at):
    print(f"Working on label {label} ({at})")
    driver.get(f'https://{es}/{at}/label/{label}?subcatid=undefined&size=100&start=0&order=asc')
    getElement(driver, '//tr[@class="odd"]')
    soup = getSoup(driver)
    ul = soup.find('ul', {"class": "nav nav-custom nav-borderless nav_tabs"})
    subcats = {"Main": "0"}
    if ul is not None:
        for a in ul.find_all('a', {"class": "nav-link"}):
            subcats[a.text.split()[0]] = a['val']
    print("Subcategories:", json.dumps(subcats, indent=4))
    d = soup.find('div', {"class": "card-body"})
    desc = ""
    if d and "found" not in d.text:
        print(d.text.strip())
        desc = d.text.strip()
    address = {}
    for subcat in subcats.keys():
        address[subcat] = []
        print(f"Working on category {subcat}")
        driver.get(f'https://{es}/{at}/label/{label}?subcatid={subcats[subcat]}&size=100&start=0&order=asc')
        soup = getSoup(driver)
        pageno = soup.find('li', {'class': 'page-item disabled'})
        if pageno is not None:
            pagenos = pageno.find_all('strong')[1].text
            print(soup.find('div', {"role": "status"}).text.strip())
            print("Total pages:", pagenos)
            for i in range(0, int(pagenos)):
                print(f"Working on page#{i + 1}")
                driver.get(f'https://{es}/{at}/label/{label}?'
                           f'subcatid={subcats[subcat]}&size=100&start={i * 100}&order=asc')
                time.sleep(1)
                getElement(driver, '//tr[@class="odd" and @role="row"]/td')
                soup = getSoup(driver)
                table = soup.find('table', {"id": f"table-subcatid-{subcats[subcat]}"})
                ths = table.find('thead').find_all('th')
                trs = table.find('tbody').find_all('tr')
                rows = []
                for tr in trs:
                    tds = tr.find_all('td')
                    if len(tds) == len(ths):
                        data = {"Subcategory": subcat, "Desc": desc, "Label": label}
                        for t in range(len(ths)):
                            try:
                                if ths[t].text == "Website":
                                    data[ths[t].text] = tds[t].find('a')['href']
                                else:
                                    data[ths[t].text.strip()] = tds[t].text
                            except:
                                print(tds)
                        rows.append(data)
                address[subcat].extend(rows)
    print(json.dumps(address, indent=4))
    threads = []
    for subcat in address.keys():
        for tr in address[subcat]:
            if at == 'accounts' or at == 'tokens':
                addr = tr['Address'] if at == 'accounts' else tr['Contract Address']
                if addr not in scraped[at]:
                    thread = threading.Thread(target=scrape, args=(driver, tr, at,))
                    thread.start()
                    threads.append(thread)
                    time.sleep(0.5)
                else:
                    print(f"{at} {addr} already scraped!")
    for thread in threads:
        thread.join()
    with open('scraped_labels.txt', 'a') as sfile:
        sfile.write(f"{label}-{at}\n")
    scraped['labels'].append(label)


def main():
    global scraped
    logo()
    time.sleep(0.5)
    driver = getChromeDriver()
    if not debug:
        reCaptchaSolver(driver)
    for x in ['labels', 'accounts', 'tokens']:
        if os.path.isfile(f"scraped_{x}.txt"):
            with open(f"scraped_{x}.txt") as afile:
                scraped[x] = afile.read().splitlines()
        else:
            scraped[x] = []
    if not os.path.isdir('CSVs'):
        os.mkdir('CSVs')
    driver.get(f'https://{es}/labelcloud')
    btnclass = 'col-md-4 col-lg-3 mb-3 secondary-container'
    getElement(driver, f'//div[@class="{btnclass}"]')
    soup = getSoup(driver)
    divs = [
        x for x in soup.find_all('div', {'class': btnclass})
        # if x.find('button')['data-url'] not in blocked
    ]
    print(f"Found {len(divs)} labels.")
    for div in divs:
        label = div.find('button')['data-url']
        for at in [a['href'].split('/')[1] for a in div.find_all('a')]:
            if f"{label}-{at}" not in scraped['labels']:
                scrapeLabel(driver, label, at)
            else:
                print(f"{label} ({at}) already scraped!")


def getChromeDriver():
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument('start-maximized')
    chrome_options.add_argument(f'user-agent={UserAgent().random}')
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    if debug:
        chrome_options.debugger_address = "127.0.0.1:9222"
    else:
        chrome_options.add_argument('--user-data-dir=C:/Selenium1/ChromeProfile')
        # chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options)
    return driver


def reCaptchaSolver(driver):
    driver.get(page_url)
    time.sleep(2)
    while "busy" in driver.current_url or "unusual traffic" in driver.page_source.lower():
        time.sleep(3)
        driver.get(page_url)
    time.sleep(1)
    if "login" not in driver.current_url:
        print(f"Already logged in as {driver.find_element(By.TAG_NAME, 'h4').text}")
        return
    driver.find_element(By.ID, "ContentPlaceHolder1_txtUserName").send_keys("tapendra")
    driver.find_element(By.ID, "ContentPlaceHolder1_txtPassword").send_keys("12345678")
    driver.find_element(By.XPATH, '//label[@for="ContentPlaceHolder1_chkRemember"]').click()
    u1 = f"https://2captcha.com/in.php?key={API_KEY}&method=userrecaptcha&googlekey" \
         f"={data_sitekey}&pageurl={page_url}&json=1&invisible=1"
    r1 = requests.get(u1)
    print(r1.json())
    time.sleep(10)
    rid = r1.json().get("request")
    u2 = f"https://2captcha.com/res.php?key={API_KEY}&action=get&id={int(rid)}&json=1"
    time.sleep(5)
    while True:
        r2 = requests.get(u2)
        print(r2.json())
        if r2.json().get("status") == 1:
            form_tokon = r2.json().get("request")
            break
        time.sleep(5)
    driver.execute_script(f'document.getElementById("g-recaptcha-response").innerHTML="{form_tokon}";')
    time.sleep(3)
    button = driver.find_element(By.XPATH, "/html/body/div[1]/main/div/form/div[8]/div[2]/input")
    driver.execute_script("arguments[0].click();", button)
    time.sleep(5)


def getSession(driver, url):
    s = requests.Session()
    s.headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/101.0.4951.67 Safari/537.36'
    }
    for cookie in driver.get_cookies():
        s.cookies.set(cookie['name'], cookie['value'])
    return BeautifulSoup(s.get(url).content, 'lxml')


def logo():
    print(r"""
    ___________  __   .__                                                   
    \_   _____/_/  |_ |  |__    ____ _______  ______  ____  _____     ____  
     |    __)_ \   __\|  |  \ _/ __ \\_  __ \/  ___/_/ ___\ \__  \   /    \ 
     |        \ |  |  |   Y  \\  ___/ |  | \/\___ \ \  \___  / __ \_|   |  \
    /_______  / |__|  |___|  / \___  >|__|  /____  > \___  >(____  /|___|  /
            \/             \/      \/            \/      \/      \/      \/ 
=================================================================================
           Etherscan labelcloud scraper by github.com/evilgenius786
=================================================================================
[+] Scrapes accounts and tokens
[+] CSV/JSON Output
_________________________________________________________________________________
""")


def getSoup(driver):
    time.sleep(1)
    return BeautifulSoup(driver.page_source, 'lxml')


def getTag(soup, tag, attrib):
    try:
        return soup.find(tag, attrib).text.strip()
    except:
        return ""


def getElement(driver, xpath):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((By.XPATH, xpath)))


def checkAccount():
    s = requests.Session()
    s.headers = {'user-agent': 'Mozilla/5.0'}
    adrs = '0xe66b31678d6c16e9ebf358268a790b763c133750'
    soup = BeautifulSoup(s.get(f'https://{es}/address/{adrs}').content, 'lxml')
    ac_data = {
        "Address": adrs,
        "Subcategory": 'Subcategory',
        "Label": 'label'
    }
    getAccount(soup, ac_data)


def checkToken():
    s = requests.Session()
    s.headers = {'user-agent': 'Mozilla/5.0'}
    adrs = '0x87d73E916D7057945c9BcD8cdd94e42A6F47f776'
    soup = BeautifulSoup(s.get(f'https://{es}/token/{adrs}').content, 'lxml')
    tk_data = {
        'Contract Address': adrs,
        "Subcategory": 'Subcategory',
        "Label": 'Label',
        "Market Cap": 'MarketCap',
    }
    getToken(soup, tk_data)


if __name__ == '__main__':
    main()
    # checkAccount()
