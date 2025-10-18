import os
import random
import time
import traceback
from itertools import product
from pathlib import Path
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
import src.utils as utils
from src.job import Job
from src.linkedIn_easy_applier import LinkedInEasyApplier
import json


class EnvironmentKeys:
    def __init__(self):
        self.skip_apply = self._read_env_key_bool("SKIP_APPLY")
        self.disable_description_filter = self._read_env_key_bool("DISABLE_DESCRIPTION_FILTER")

    @staticmethod
    def _read_env_key(key: str) -> str:
        return os.getenv(key, "")

    @staticmethod
    def _read_env_key_bool(key: str) -> bool:
        return os.getenv(key) == "True"

class LinkedInJobManager:
    def __init__(self, driver):
        self.driver = driver
        self.set_old_answers = set()
        self.easy_applier_component = None

    def set_parameters(self, parameters):
        self.company_blacklist = parameters.get('companyBlacklist', []) or []
        self.title_blacklist = parameters.get('titleBlacklist', []) or []
        self.positions = parameters.get('positions', [])
        self.locations = parameters.get('locations', [])
        self.base_search_url = self.get_base_search_url(parameters)
        self.seen_jobs = []
        resume_path = parameters.get('uploads', {}).get('resume', None)
        if resume_path is not None and Path(resume_path).exists():
            self.resume_path = Path(resume_path)
        else:
            self.resume_path = None
        self.output_file_directory = Path(parameters['outputFileDirectory'])
        self.env_config = EnvironmentKeys()
        #self.old_question()

    def set_gpt_answerer(self, gpt_answerer):
        self.gpt_answerer = gpt_answerer

    def set_resume_generator_manager(self, resume_generator_manager):
        self.resume_generator_manager = resume_generator_manager

    def start_applying(self):
        self.easy_applier_component = LinkedInEasyApplier(self.driver, self.resume_path, self.set_old_answers, self.gpt_answerer, self.resume_generator_manager)
        searches = list(product(self.positions, self.locations))
        random.shuffle(searches)
        page_sleep = 0
        minimum_time = 60 * 1
        minimum_page_time = time.time() + minimum_time

        for position, location in searches:
            location_url = "&location=" + location
            job_page_number = -1
            utils.printyellow(f"Starting the search for {position} in {location}.")

            try:
                while True:
                    page_sleep += 1
                    job_page_number += 1
                    utils.printyellow(f"Going to job page {job_page_number}")
                    self.next_job_page(position, location_url, job_page_number)
                    time.sleep(random.uniform(1.5, 3.5))
                    utils.printyellow("Starting the application process for this page...")
                    self.apply_jobs()
                    utils.printyellow("Applying to jobs on this page has been completed!")

                    time_left = minimum_page_time - time.time()
                    if time_left > 0:
                        utils.printyellow(f"Sleeping for {time_left} seconds.")
                        time.sleep(time_left)
                        minimum_page_time = time.time() + minimum_time
                    if page_sleep % 5 == 0:
                        sleep_time = random.randint(5, 34)
                        utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                        time.sleep(sleep_time)
                        page_sleep += 1
            except Exception:
                traceback.format_exc()
                pass
            time_left = minimum_page_time - time.time()
            if time_left > 0:
                utils.printyellow(f"Sleeping for {time_left} seconds.")
                time.sleep(time_left)
                minimum_page_time = time.time() + minimum_time
            if page_sleep % 5 == 0:
                sleep_time = random.randint(50, 90)
                utils.printyellow(f"Sleeping for {sleep_time / 60} minutes.")
                time.sleep(sleep_time)
                page_sleep += 1

    def apply_jobs(self):
        try:
            print("APPLY JOBS 106")
            no_jobs_element = self.driver.find_element(By.CLASS_NAME, 'jobs-search-two-pane__no-results-banner--expand')
            if 'No matching jobs found' in no_jobs_element.text or 'unfortunately, things aren' in self.driver.page_source.lower():
                raise Exception("No more jobs on this page")
        except NoSuchElementException:
            pass
        
        print("APPLY JOBS 112")
        
        try:
            job_results = self.driver.find_element(By.XPATH, "//*[@id='main']/div/div[2]/div[1]/div")
            print("APPLY JOBS 115 - Found job results container")
        except NoSuchElementException:
            print("APPLY JOBS 115 - No job results container found")
            raise Exception("No job results container found on page")

        scrollable_container = self.driver.find_element(By.XPATH, "/html/body/div[5]/div[3]/div[4]/div/div/main/div/div[2]/div[1]/div")
        utils.scroll_slow(self.driver, scrollable_container)
        utils.scroll_slow(self.driver, job_results, step=300, reverse=True)

        job_list_elements = self.driver.find_elements(By.CSS_SELECTOR, "[data-job-id]")
        print(f"TEST - Found {len(job_list_elements)} job elements")
        print(f"TEST - Found {job_list_elements}")
        print(f"TEST - Found {job_list_elements[0]}")
        print(f"TEST - Found INFORMATION {job_list_elements[0].text.split(chr(10))}")
        print(f"TEST - Found INFORMATION {job_list_elements[1].text.split(chr(10))}")


        job_list = []
        for job_element in job_list_elements:
            # job_title, company,job_location, link, apply_method = self.extract_job_information_from_tile(job_element)
            
            job_title = job_element.get_attribute('job-card-list__title')
            company = job_element.get_attribute('data-job-company')
            job_location = job_element.get_attribute('data-job-location')
            link = job_element.get_attribute('data-job-link')
            apply_method = job_element.get_attribute('data-job-apply-method')
            # Create Job object with only the extracted fields
            job = Job(
                title=job_title,
                company=company,
                location=job_location,  
                link=link,
                apply_method=apply_method
            )
            job_list.append(job)
            
        print(f"TEST - Created {len(job_list)} job objects")
 
        for job in job_list:
            if self.is_blacklisted(job.title, job.company, job.link):
                utils.printyellow(f"Blacklisted {job.title} at {job.company}, skipping...")
                self.write_to_file(job, "skipped")
                continue
            try:
                if job.apply_method not in {"Continue", "Applied", "Apply"}:
                    self.easy_applier_component.job_apply(job)
                    self.write_to_file(job, "success")
            except Exception as e:
                utils.printred(traceback.format_exc())
                self.write_to_file(job, "failed")
                continue
        
    def write_to_file(self, job, file_name):
        pdf_path = Path(job.pdf_path).resolve()
        pdf_path = pdf_path.as_uri()
        data = {
            "company": job.company,
            "job_title": job.title,
            "link": job.link,
            "job_recruiter": job.recruiter_link,
            "job_location": job.location,
            "pdf_path": pdf_path
        }
        file_path = self.output_file_directory / f"{file_name}.json"
        if not file_path.exists():
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump([data], f, indent=4)
        else:
            with open(file_path, 'r+', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                except json.JSONDecodeError:
                    existing_data = []
                existing_data.append(data)
                f.seek(0)
                json.dump(existing_data, f, indent=4)
                f.truncate()

    def get_base_search_url(self, parameters):
        url_parts = []
        if parameters['remote']:
            url_parts.append("f_CF=f_WRA")
        experience_levels = [str(i+1) for i, (level, v) in enumerate(parameters.get('experienceLevel', {}).items()) if v]
        if experience_levels:
            url_parts.append(f"f_E={','.join(experience_levels)}")
        url_parts.append(f"distance={parameters['distance']}")
        job_types = [key[0].upper() for key, value in parameters.get('jobTypes', {}).items() if value]
        if job_types:
            url_parts.append(f"f_JT={','.join(job_types)}")
        date_mapping = {
            "all time": "",
            "month": "&f_TPR=r2592000",
            "week": "&f_TPR=r604800",
            "24 hours": "&f_TPR=r86400"
        }
        date_param = next((v for k, v in date_mapping.items() if parameters.get('date', {}).get(k)), "")
        url_parts.append("f_LF=f_AL")  # Easy Apply
        base_url = "&".join(url_parts)
        return f"?{base_url}{date_param}"
    
    def next_job_page(self, position, location, job_page):
        self.driver.get(f"https://www.linkedin.com/jobs/search/{self.base_search_url}&keywords={position}{location}&start={job_page * 25}")
    
    def extract_job_information_from_tile(self, job_tile):
        print(f"TEST - Found {len(job_list_elements)} job elements in extract_job_information_from_tile")
        job_title, company, job_location, apply_method, link = "", "", "", "", ""
        print(f"TEST - Found {len(job_list_elements)} job elements in extract_job_information_from_tile")

        try:
            # Get job title and link from the title element
            title_element = job_tile.find_element(By.CLASS_NAME, 'job-card-list__title')
            job_title = title_element.text
            link = title_element.get_attribute('href').split('?')[0]
        except:
            pass
            
        try:
            # Get company name
            company = job_tile.find_element(By.CLASS_NAME, 'artdeco-entity-lockup__subtitle').text
        except:
            pass
        try:
            apply_method = job_tile.find_element(By.CLASS_NAME, 'job-card-list__footer-wrapper').text
        except:
            apply_method = "Applied"

        return job_title, company, job_location, link, apply_method
    
    def is_blacklisted(self, job_title, company, link):
        job_title_words = job_title.lower().split(' ')
        title_blacklisted = any(word in job_title_words for word in self.title_blacklist)
        company_blacklisted = company.strip().lower() in (word.strip().lower() for word in self.company_blacklist)
        link_seen = link in self.seen_jobs
        return title_blacklisted or company_blacklisted or link_seen
