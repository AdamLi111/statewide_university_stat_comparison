import numpy as np
from bs4 import BeautifulSoup
from urllib.request import urlopen, Request
import re
from geopy.geocoders import Nominatim
import time
import os
import requests


from matplotlib import pyplot as plt

import json

def scrape_US():
    '''
    Scrapes tuition data for all 4-year private universities in the U.S.
    :return: a dictionary { university_name: tuition }
    '''
    data = {}
    max_pages = 10

    for page in range(1, max_pages + 1):
        url = f"https://www.collegesimply.com/colleges/search?sort=&place=&fr=&fm=tuition-in-state&lm=&years=4&gpa=&sat=&act=&admit=comp&field=&major=&radius=300&zip=&state=&size=&tuition-fees=&net-price=&page={page}&pp=/colleges/search"
        print(f"🔍 Scraping page {page}...")

        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            html = urlopen(req)
            bs = BeautifulSoup(html.read(), "html.parser")
        except Exception as e:
            print(f"❌ Error opening page {page}: {e}")
            break

        cards = bs.select('div.col-sm-6.col-xl-4.mb-5.hover-animate')

        if not cards:
            print("✅ No more results found. Ending scrape.")
            break

        for card in cards:
            name_tag = card.find('h3', class_='h6 card-title')
            h4_tag = card.find('h4')
            tuition_tag = h4_tag.find('span', class_='text-primary') if h4_tag else None

            if name_tag and tuition_tag:
                full_name = name_tag.get_text(strip=True)
                name = full_name.split('Private')[
                    0].strip() if 'Private' in full_name else full_name  # Extract university name
                tuition = int(re.sub(r'[^0-9]', '', tuition_tag.get_text(strip=True)))  # Convert tuition to int
                data[name] = tuition

    print(f"\n✅ Finished scraping {len(data)} universities.\n")
    return data


def get_state(university_name):
    '''
    use an API called geolocator to get the university's state based on its name
    :param university_name: self-explanatory name
    :return: the states of the universities
    '''
    geolocator = Nominatim(user_agent="university_locator")
    try:
        location = geolocator.geocode(university_name + ", USA", timeout=1)
        if location:
            return location.address.split(",")[-3].strip()  # Extract state name
        return None
    except Exception as e:
        print(f"Error fetching {university_name}: {e}")
        return None



def get_rating(university_states):
    ratings = {}
    missing_universities = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/98.0.4758.102 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/"
    }

    for name, state in university_states.items():
        name_cleaned = "-".join(name.lower().split())
        state_cleaned = "-".join(state.lower().split())
        if "&" in state_cleaned:
            state_cleaned = "johnson-and-wales-university-providence"
        link = f"https://www.collegesimply.com/colleges/{state_cleaned}/{name_cleaned}/reviews/"
        try:
            response = requests.get(link, headers=headers)
            # Check if response status code is 200 (OK)
            response.raise_for_status()
            bs = BeautifulSoup(response.text, "html.parser")
            rating_spans = bs.select("div.col-md-6 span.avatar-title.rounded-circle")
            ratings[name] = [span.text.strip() for span in rating_spans] if rating_spans else ["NA"]
            print(f"✅ Ratings for {name}: {ratings[name]}")
        except requests.exceptions.HTTPError as http_err:
            print(f"⚠️ Error fetching ratings for {name}: HTTP Error {http_err.response.status_code}")
            ratings[name] = ["NA"]
            missing_universities.append((name, link))
        except Exception as e:
            print(f"⚠️ Error fetching ratings for {name}: {e}")
            ratings[name] = ["NA"]
            missing_universities.append((name, link))

        # Delay to prevent being rate-limited
        time.sleep(1)

    if missing_universities:
        print("\n🚨 WARNING: The following universities returned errors:")
        for uni, url in missing_universities:
            print(f"- {uni} → {url}")
    return ratings


def parse_ratings():
    '''
    parse the uni_ratings.json file and return it in a dictionary
    :return: a dictionary that contains all ratings data
    '''
    with open('uni_ratings_US.json', 'r') as infile:
        uni_ratings = json.load(infile)
    cleaned_ratings = {}
    for university, ratings in uni_ratings.items():
        new_ratings = []
        for rating in ratings:
            # Check if the rating is in the form "7/10"
            if isinstance(rating, str) and '/' in rating:
                try:
                    new_ratings.append(int(rating.split('/')[0]))
                except ValueError:
                    # If conversion fails, set a default value (or handle it differently)
                    new_ratings.append(int(0))
            else:
                # If the rating is "NA" or another value, handle accordingly
                new_ratings.append(int(0))
        cleaned_ratings[university] = new_ratings
    return cleaned_ratings

def get_edu_score(dct: dict):
    '''
    test run that draws the first couple of universities' radar chart
    :param dct: uni_ratings dictionary
    :return: a dictionary that contains the educational score of the universities
    '''
    edu_score = {}
    for k, v in dct.items():
        edu_score[k] = compute_score(v)
    return edu_score


def get_states(tuition: dict, cache_file='data/univ_states.json'):
    '''
    Get or load states for universities. Saves progress to avoid repeating.
    :param tuition: dictionary of {university: tuition}
    :param cache_file: path to JSON file to load/save cached states
    :return: dictionary {university: state}
    '''
    # Load from cache if exists
    try:
        with open(cache_file, 'r') as f:
            university_states = json.load(f)
    except FileNotFoundError:
        university_states = {}

    geolocator = Nominatim(user_agent="university_locator")

    for university in tuition:
        if university in university_states:
            continue  # Skip already fetched

        retries = 3
        while retries > 0:
            try:
                location = geolocator.geocode(university + ", USA", timeout=10)
                if location:
                    state = location.address.split(",")[-3].strip()
                    university_states[university] = state
                    print(f"✅ Got state for {university}: {state}")
                else:
                    university_states[university] = "Unknown"
                    print(f"❌ No result for {university}")
                break
            except Exception as e:
                print(f"⚠️ Error fetching {university}: {e}")
                retries -= 1
                time.sleep(2)

        # Save progress every 5 entries
        if len(university_states) % 5 == 0:
            with open(cache_file, 'w') as f:
                json.dump(university_states, f, indent=2)

        time.sleep(1)

    # Final save
    with open(cache_file, 'w') as f:
        json.dump(university_states, f, indent=2)

    return university_states


def plot_linear_regression(tuition_file, edu_scores_file):
    # Load tuition fees data
    with open(tuition_file, 'r') as f:
        tuition_data = json.load(f)

    # Load educational scores data
    with open(edu_scores_file, 'r') as f:
        edu_scores = json.load(f)

    # Extract common universities
    common_unis = set(tuition_data.keys()).intersection(edu_scores.keys())

    # Prepare data lists
    x = []  # tuition fees
    y = []  # educational scores
    names = []  # university names
    for uni in common_unis:
        x.append(tuition_data[uni])
        y.append(edu_scores[uni])
        names.append(uni)

    # Convert lists to numpy arrays for regression
    x_np = np.array(x)
    y_np = np.array(y)

    # Perform linear regression: y = m*x + b
    m, b = np.polyfit(x_np, y_np, 1)

    # Generate points for regression line
    x_line = np.linspace(min(x_np), max(x_np), 100)
    y_line = m * x_line + b

    # Plot scatter and regression line
    plt.figure(figsize=(10, 6))
    plt.scatter(x_np, y_np, color='blue', label='Data Points')
    plt.plot(x_line, y_line, color='red', label=f'Linear Regression: y={m:.2e}x + {b:.2f}')

    # Annotate each point with the university name
    for xi, yi, name in zip(x_np, y_np, names):
        plt.annotate(name, (xi, yi), textcoords="offset points", xytext=(5, 5), fontsize=8)

    plt.xlabel("Tuition Fees")
    plt.ylabel("Educational Score")
    plt.title("Linear Regression: Tuition Fees vs Educational Score")
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():

    ###########################################################################
    # the following code will do the web scraping job, which takes a long time.
    # Since we've already scraped some data, which have been stored in json files
    # only run the following code when you actually want to scrape for more data.

    #tuition_data = scrape_NE()
    #print(tuition_data)
    #get_states(tuition_data)
    #print(local_states)
    #print(get_rating(local_states))
    #us_data = scrape_US()
    ###########################################################################

    plot_linear_regression(tuition_file='tuition_US.json', edu_scores_file='parsed_ratings.json')

if __name__ == "__main__":
    main()
