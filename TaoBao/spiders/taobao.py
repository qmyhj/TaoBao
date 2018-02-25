# -*- coding: utf-8 -*-
import scrapy
from selenium import webdriver
from ..settings import QUESTION, DEFAULT_BROWSER
from scrapy.xlib.pydispatch import dispatcher
from scrapy import signals
from ..items import TaobaoItem
import re
import time
import requests
from PIL import Image
from urllib.parse import urljoin
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class TaobaoSpider(scrapy.Spider):
    name = 'taobao'
    allowed_domains = ['taobao.com']
    start_urls = ['https://s.taobao.com/search?q={q}'.format(q=QUESTION)]

    """设置chrome不加载图片"""
    chrome_opt = webdriver.ChromeOptions()
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_opt.add_experimental_option("prefs", prefs)

    def __init__(self):
        super(TaobaoSpider, self).__init__()
        self.login_url = 'https://login.taobao.com/member/login.jhtml?tpl_redirect_url=https%3A%2F%2Fwww.tmall.com&style=miniall&enup=true&newMini2=true&full_redirect=true&sub=true&from=tmall&allp=assets_css%3D3.0.10/login_pc.css&pms=1519536513735'

        if DEFAULT_BROWSER == 'Chrome':
            self.browser = webdriver.Chrome(chrome_options=self.chrome_opt)
        elif DEFAULT_BROWSER == 'PhantomJS':
            self.browser = webdriver.PhantomJS()
        self.browser.maximize_window()
        self.wait = WebDriverWait(self.browser, 5)
        dispatcher.connect(self.spider_closed, signal=signals.spider_closed)
        self.download_img()
        self.wait_for_login()

    """下载二维码扫码登录"""
    def download_img(self):
        self.browser.get(self.login_url)
        img_tag = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, 'img')))
        img_url = img_tag.get_attribute('src')
        self.logger.debug('正在下载二维码，请耐心等待..........')
        r = requests.get(img_url)
        with open('captcha.jpg', 'wb') as f:
            f.write(r.content)
        self.logger.debug('请扫二维码登录淘宝：.............')
        image = Image.open('captcha.jpg')
        image.show()

    """等待登录"""
    def wait_for_login(self, timeout=60):
        while True:
            time1 = time.time()
            if self.login_url == self.browser.current_url:
                time.sleep(3)
                if time.time() - time1 > timeout:
                    self.logger.debug('二维码已失效正在刷新:..........')
                    self.download_img()
            else:
                break

    def spider_closed(self):
        self.browser.close()

    """解析商品列表页信息"""
    def parse(self, response):
        goods = response.css('div.item.J_MouserOnverReq')
        for good in goods:
            title = good.css('div.row.row-2.title a.J_ClickStat::text').extract()
            if isinstance(title, list):
                title = ''.join(title).strip()
            price = good.css('div.price.g_price.g_price-highlight strong::text').extract_first()
            free_shipping = 'Yes' if good.css('div.ship.icon-service-free') else 'No'
            month_sale = good.css('div.deal-cnt::text').extract_first()
            month_sale = re.match(r'\d+', month_sale).group(0)
            goods_url = good.css('div.row.row-2.title a.J_ClickStat::attr(href)').extract_first()

            shop = good.xpath('//div[@class="shop"]/a/span[2]/text()').extract_first()
            shop_type = '天猫' if good.css('span.icon-service-tianmao') else '淘宝'
            addr = good.css('div.location::text').extract_first()
            data = {
                'title': title,
                'price': price,
                'free_shipping': free_shipping,
                'month_sale' : month_sale,
                'goods_url': goods_url,
                'shop': shop,
                'shop_type': shop_type,
                'addr': addr
            }

            yield scrapy.Request(urljoin('https:', goods_url), meta={'data': data}, callback=self.parse_grade)
        """ 获取下一页链接"""
        try:
            next_key = response.css('li.next a::attr(data-key)').extract_first()
            next_value = response.css('li.next a::attr(data-value)').extract_first()
            next_url = self.start_urls[0] + '&' + next_key + '=' + next_value
            self.logger.debug('tring to crawl newpage .............')
            yield scrapy.Request(next_url, callback=self.parse)
        except:
            self.logger.info('all pages have been crawled')

    """解析商品详情页信息"""
    def parse_grade(self, response):
        item = TaobaoItem()
        data = response.meta['data']
        item['title'] = data['title']
        item['price'] = data['price']
        item['free_shipping'] = data['free_shipping']
        item['month_sale'] = data['month_sale']
        item['goods_url'] = data['goods_url']
        item['shop'] = data['shop']
        item['shop_type'] = data['shop_type']
        item['addr'] = data['addr']

        """淘宝页面格式较多，这里取其中常见的两种"""
        if item['shop_type'] == '天猫':
            same_grade = response.css('div.shopdsr-score.shopdsr-score-up-ctrl span::text').extract()
            if not same_grade:
                same_grade = response.css('#shop-info div.main-info span::text').extract()
        else:
            same_grade = response.css('div.tb-shop-rate a::text').extract()
            if not same_grade:
                same_grade = response.css('ul.shop-service-info-list em::text').extract()
        if len(same_grade) == 3:
            item['same_grade'] = float(same_grade[0].strip())
            item['service_grade'] = float(same_grade[1].strip())
            item['shipping_grade'] = float(same_grade[2].strip())

        if len(item.keys()) != 11:
            for field in item.fields:
                if field not in item.keys():
                    item[field] = None

        yield item

