from bs4 import BeautifulSoup
import glob, os
from airflow.hooks.postgres_hook import PostgresHook
from helpers import SqlQueries
from psycopg2 import sql


def parse_jobs_vacancies(soup, pgsql, cursor, company_infos):
    jobListings = soup.select('.details-row.jobs > .content > .listing-row')
    num_job_listings = 0
    jobs = []
    for jobListing in jobListings:
        jobVacancyLink = jobListing.select_one('.top > .title > a')
        jobVacancyTags = jobListing.select_one('.top > .title > .tags')
        jobVacancyCompensations = jobListing.select_one('.top > .compensation')

        job_title = jobVacancyLink.get_text()
        job_remote_url = jobVacancyLink['href']
        tags = jobVacancyTags.get_text().split('·')
        compensations = jobVacancyCompensations.get_text().split('·')
        parsed_compensations = {}
        if len(compensations) >= 1:
            parsed_compensations['description_salary_range'] = compensations[0].strip()
            if '–' in parsed_compensations['description_salary_range']:
                parsed_range = list(map(lambda x: x.strip(), parsed_compensations['description_salary_range'].split('–')))
                if len(parsed_range) >= 1:
                    parsed_compensations['salary'] = parsed_range[0]
                if len(parsed_range) >= 2:
                    parsed_compensations['salary_max'] = parsed_range[1]
                else:
                    parsed_compensations['salary_max'] = parsed_range[0]
            else:
                print('no risks')
        if len(compensations) >= 2:
            parsed_compensations['description_equity_range'] = compensations[1].strip()

        for tag_tag in tags:
            cursor.execute(SqlQueries.upsert_tags_row, {'tag': tag_tag})
        
        splitted_remote_url = job_remote_url.split('/')

        job_infos = {
            'id': splitted_remote_url[ (len(splitted_remote_url) - 1) ],
            'provider_id': 'angels_co',
            'remote_id_on_provider': splitted_remote_url[ (len(splitted_remote_url) - 1) ],
            'remote_url': job_remote_url,
            'location': None,
            'currency_code': None,
            'company_id': company_infos['id'],
            'company_name': company_infos['name'],
            'title': job_title,
            'description': '',
            'tags': ",".join(list(map(lambda x: x.strip(), tags))),
            **parsed_compensations,
            'salary_frequency': None,
            'has_relocation_package': True,
            'expires_at': None,
            'published_at': None,
        }
        cursor.execute(SqlQueries.upsert_jobs_row, job_infos)
        jobs.append(job_infos)
        num_job_listings += 1
    if num_job_listings > 1:
        # print('MORE THAN ONE!')
        print(jobs)
        return True
    return False


def parse_company_infos(soup, pgsql, cursor):
    companyLinkElements = soup.select('.header-info .browse-table-row-name .startup-link')
    for companyLinkElement in companyLinkElements:
        remote_url = companyLinkElement['href']
        remote_url_fragments = remote_url.split('/')
        remote_url_framengs_count = len(remote_url_fragments)
        remote_id = remote_url_fragments[remote_url_framengs_count - 2]
        company_infos = {
            'id': remote_id,
            'name': companyLinkElement.get_text(),
            'remote_url': remote_url
        }
        cursor.execute(SqlQueries.upsert_companies_row, company_infos)
        return company_infos


def parse_html_scrapped(file_path, pgsql, cursor):
    f = open(file_path, "r")
    if f.mode == 'r':
        soup = BeautifulSoup(f.read(), features="html.parser")
        company_infos = parse_company_infos(soup, pgsql, cursor)
        return parse_jobs_vacancies(soup, pgsql, cursor, company_infos)
        # print(company_infos)


def main():
    # 0 - Prepare the database connection
    pgsql = PostgresHook(postgres_conn_id="pgsql")
    cur = pgsql.get_cursor()

    # 1 - open the output directory

    for file in os.listdir("crawlers/output"):
        if file.endswith(".html"):
            parse_html_scrapped(os.path.join("crawlers/output", file), pgsql, cur)
    # 2 - read each html file in the output directory and write them to the database


if __name__ == '__main__':
    main()