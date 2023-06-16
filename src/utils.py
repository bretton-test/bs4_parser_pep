from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from requests import RequestException
from tqdm import tqdm

from constants import PEP_DOC_URL
from exceptions import CompareTagException, ParserFindTagException


@dataclass()
class Pep:
    declared_status: str
    number: str
    title: str
    authors: str
    link: str
    real_status: str


def get_response(session, url):
    try:
        response = session.get(url)
        response.encoding = 'utf-8'
        return response
    except RequestException:
        logging.exception(
            f'Возникла ошибка при загрузке страницы {url}', stack_info=True
        )


def find_tag(soup, tag, attrs=None):
    searched_tag = soup.find(tag, attrs=(attrs or {}))
    if searched_tag is None:
        error_msg = f'Не найден тег {tag} {attrs}'
        logging.error(error_msg, stack_info=True)
        raise ParserFindTagException(error_msg)
    return searched_tag


def get_pep_keys(soup, pep_keys):
    pep_type_key_tags = soup.find_all('li')
    for tag in pep_type_key_tags:
        key = find_tag(tag, 'strong').text
        value = find_tag(tag, 'em').text
        pep_keys[key] = value


def check_status(pep, pep_statuses):
    try:
        status = pep.declared_status[1:2]
        if not status:
            status = '<No letter>'
        declared_status = pep_statuses.get(status)
        if declared_status[0] != pep.real_status[0]:
            logging.info(f'Несовпадающие статусы:{pep.link}')
            logging.info(f'Статус в карточке: {pep.real_status}')
            logging.info(f'Ожидаемый статус: {declared_status}')
    except KeyError:
        err_msg = (
            f'Возникла ошибка при сравнении статусов pep{pep.number}'
            f' ожидаемый статус:{pep.declared_status}'
            f' реальный статус:{pep.real_status}'
        )
        logging.exception(err_msg, stack_info=True)
        raise CompareTagException(err_msg)


def get_peps(soup, peps, session):
    pep_statuses = {}
    get_pep_keys(
        find_tag(soup, 'section', attrs={'id': 'pep-status-key'}),
        pep_statuses,
    )
    peps_info_section = find_tag(
        soup, 'section', attrs={'id': 'index-by-category'}
    )
    peps_info_tags = peps_info_section.find_all('tr')
    for tag in tqdm(peps_info_tags):
        link_tag = tag.find('a')
        if link_tag:
            info = tag.text.split('\n')[:4]
            link = urljoin(PEP_DOC_URL, link_tag['href'])
            real_status = get_real_status(session, link)
            info.append(link)
            info.append(real_status)
            pep = Pep(*info)
            check_status(pep, pep_statuses)
            peps[int(pep.number)] = pep


def cook_some_soup(session, url):
    response = get_response(session, url)
    response.encoding = 'utf-8'
    return BeautifulSoup(response.text, features='lxml')


def get_real_status(session, link):
    if not link:
        return ''
    soup = cook_some_soup(session, link)
    pep_section = find_tag(soup, 'section', attrs={'id': 'pep-content'})
    pep_key = [
        item.text for item in find_tag(pep_section, 'dl').find_all('dt')
    ]
    pep_info = [
        item.text for item in find_tag(pep_section, 'dl').find_all('dd')
    ]
    pep_infos = dict(zip(pep_key, pep_info))
    return pep_infos["Status:"]
