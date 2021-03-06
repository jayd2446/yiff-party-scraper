import os
import requests
import socket
import argparse
from lxml import html
from time import sleep 
from requests.adapters import HTTPAdapter
from urllib.parse import urlparse
from urllib3.exceptions import ReadTimeoutError
from requests.packages.urllib3.util.retry import Retry

def failedLinks(link, failedDirectory):

    with open(failedDirectory, "a") as failed:
        failed.write(suppliedLink+"\n")

parser = argparse.ArgumentParser(description="scrape files from yiff.party posts")
groupsParser = parser.add_mutually_exclusive_group()
groupsParser.add_argument("--links", type=str, nargs="+", const=None, help="take links from STDI")
groupsParser.add_argument("--read", metavar="file.txt", type=argparse.FileType("r", encoding="UTF-8"), const=None, help="read links from file")
parser.add_argument("--dest", type=str, nargs="?", default=os.getcwd(), help="specify download directory")
parser.add_argument("--timeout", type=int, nargs="?", default=60, help="timeout in seconds for requests")
parser.add_argument("--delay", type=int, nargs="?", default=5, help="seconds to wait between downloads")
parser.add_argument("--continous", action="store_true", default=False, help="paginate automatically and scrap next pages")
parser.add_argument("--version", action="version", version="yiff_scraper 1.0")
args = parser.parse_args()

SKIP = "https_www.dropbox.com_static_images_spectrum-icons_generated_content_content-folder_dropbox-large.png"
HEADERS = { "User-Agent" : "Opera/9.80 (Linux armv7l) Presto/2.12.407 Version/12.51 , D50u-D1-UHD/V1.5.16-UHD (Vizio, D50u-D1, Wireless)"}
RETRIES = Retry(total=10, backoff_factor=3)
ERASE = "\033[2K"
DOMAIN = "yiff.party"
TIMEOUT = args.timeout
SLEEP = args.delay
CONTINUE = args.continous
DESTINATION = os.path.abspath(args.dest)
FILE_COUNTER = 0

#check if atleast one option is passed
if not (args.read or args.links):
    print("[-] No options specified, use --help for available options")
    exit()

else:
    if args.links:
        suppliedLinks = list(dict.fromkeys(args.links)) 
    else:
        suppliedLinks = list(dict.fromkeys(list(args.read.read().splitlines())))
        args.read.close()
print(f"[+] Download folder: {DESTINATION}\n")

with requests.Session() as session:
    session.mount("https://", HTTPAdapter(max_retries=RETRIES)) #HTTP adapter mount to attempt retries

    for suppliedLink in suppliedLinks:

        suppliedLink = suppliedLink.strip()
        if not urlparse(suppliedLink).netloc == DOMAIN: #check if URl is of yiff.party, if not, ignore it
            print(f"[-] {suppliedLink} doesn't belong to {DOMAIN}, skipping it")
            continue

        print(f"[*] Getting page: {suppliedLink}", end="\r", flush=True)

        try:
            pageResp = session.get(suppliedLink, headers=HEADERS, timeout=TIMEOUT)
            pageResp.raise_for_status()

        except requests.exceptions.ConnectionError as connErr:
            failedLinks(suppliedLink, failedDirectory)
            print(connErr)
            continue
    
        except (socket.timeout, ReadTimeoutError, requests.Timeout) as timeoutErr:
            failedLinks(suppliedLink, failedDirectory)
            print(timeoutErr)
            continue

        except requests.exceptions.HTTPError as err:
            failedLinks(suppliedLink, failedDirectory)
            print(err)
            continue
        
        print(ERASE, end="\r", flush=True)
        print(f"[+] {suppliedLink}, page retrieved\n")            
        pageTree = html.fromstring(pageResp.text)
        pageTree.make_links_absolute(suppliedLink)
        creatorName = pageTree.xpath("//span[@class='yp-info-name']/text()")[0].strip()
        patreonName = pageTree.xpath("//span[@class='yp-info-name']/small/text()")[0].strip()
        creatorName = creatorName+patreonName
        creatorDirectory = os.path.join(DESTINATION, creatorName)
        failedDirectory = os.path.join(creatorDirectory, "failed_links.txt")
        os.makedirs(creatorDirectory, exist_ok=True)
        if CONTINUE:
            nextPage = pageTree.xpath("//a[@class='btn pag-btn pag-btn-bottom'][1]/@href")
            if nextPage: 
                nextPage = nextPage[0]
                index = suppliedLinks.index(suppliedLink) + 1
                suppliedLinks.insert(index, nextPage)         

        allMedia = pageTree.xpath("//div[@class='card-attachments']//a/@href")
        if not allMedia:
            allMedia = pageTree.xpath("//div[@class='card-action']//a/@href")

        for media in allMedia:

            if SKIP in media:
                continue
            
            filename = f"{FILE_COUNTER}_{media.strip('/').split('/')[-1]}"
            filepath = os.path.join(creatorDirectory, filename)

            try:
                fileData = session.head(media, headers=HEADERS, timeout=TIMEOUT)
                try:
                    fileSize = int(fileData.headers["Content-Length"])
                except KeyError:
                    fileSize = 0
                if os.path.isfile(filepath):

                    localFileSize = os.stat(filepath).st_size
                    if localFileSize == fileSize:
                        FILE_COUNTER += 1
                        continue
                    else:
                        diff = int(fileSize) - int(localFileSize)
                        if not diff == int(fileSize):
                            HEADERS["Range"] = f"bytes={diff}-{fileSize}"

                        fileResp = session.get(media, headers=HEADERS, stream=True, timeout=TIMEOUT)
                        fileResp.raise_for_status()
                else:
                    fileResp = session.get(media, headers=HEADERS, stream=True, timeout=TIMEOUT)
                    fileResp.raise_for_status()

            except requests.exceptions.ConnectionError as connErr:
                failedLinks(media, failedDirectory)
                print(connErr)
                continue
        
            except (socket.timeout, ReadTimeoutError, requests.Timeout) as timeErr:
                failedLinks(media, failedDirectory)
                print(timeErr)
                continue
        
            except requests.exceptions.HTTPError as err:
                failedLinks(media, failedDirectory)
                print(err)
                continue
        
            
            with open(filepath, "wb") as file:

                print(ERASE, end="\r", flush=True)
                print(f"[+] Downloading file: {filename}, have downloaded {FILE_COUNTER} files", end="\r", flush=True)

                for iterData in fileResp.iter_content(chunk_size=2**20): 
                    if iterData:
                        file.write(iterData) 
                
                FILE_COUNTER += 1
                if FILE_COUNTER % 4 == 0 :
                    sleep(int(SLEEP) + 5)
                else:
                    sleep(SLEEP)
                    
print(ERASE, end="\r", flush=True)
print(f"[+] {FILE_COUNTER} files downloaded")
