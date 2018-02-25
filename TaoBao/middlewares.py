# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/spider-middleware.html

from fake_useragent import UserAgent
from scrapy.http import HtmlResponse
import logging


class ChromeMiddleware(object):

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def process_request(self, request, spider):
        browser = spider.browser
        browser.get(request.url)
        """模拟下拉"""
        # browser.execute_script('window.scrollTo(0,document.body.scrollHeight);var leftOfPage = document.body.scrollHeight;return leftOfPage;')
        self.logger.debug('getting ' + request.url)
        return HtmlResponse(url=request.url, body=browser.page_source, request=request, encoding='utf-8')

