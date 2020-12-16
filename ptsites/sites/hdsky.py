import json
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

from ..schema.nexusphp import NexusPHP
from ..schema.site_base import SignState
from ..schema.site_base import SiteBase
from ..utils.baidu_ocr import BaiduOcr

try:
    from PIL import Image
except ImportError:
    Image = None

# auto_sign_in
BASE_URL = 'https://hdsky.me/'
IMAGE_HASH_URL = urljoin(BASE_URL, '/image_code_ajax.php')
IMAGE_URL = urljoin(BASE_URL, '/image.php?action=regimage&imagehash={}')
URL = urljoin(BASE_URL, '/showup.php')
SUCCEED_REGEX = '已签到|{"success":true,"message":\\d+}'
WRONG_REGEX = '{"success":false,"message":"invalid_imagehash"}'

# iyuu_auto_reseed
# hdsky:
#   headers:
#     cookie: '{ cookie }'
#     user-agent: '{? headers.user_agent ?}'
TORRENT_PAGE_URL = urljoin(BASE_URL, '/details.php?id={}&hit=1')


class MainClass(NexusPHP):
    @staticmethod
    def build_sign_in(entry, config):
        SiteBase.build_sign_in_entry(entry, config, URL, SUCCEED_REGEX, base_url=BASE_URL,
                                     wrong_regex=WRONG_REGEX)

    @staticmethod
    def build_reseed(entry, site, passkey, torrent_id):
        SiteBase.build_reseed_from_page(entry, passkey, torrent_id, BASE_URL, TORRENT_PAGE_URL,
                                        '/download\\.php\\?id=\\d+&passkey=.+?(?=")')

    def sign_in(self, entry, config):
        if not Image:
            entry.fail_with_prefix('Dependency does not exist: [PIL]')
            return
        entry['base_response'] = base_response = self._request(entry, 'get', BASE_URL)
        sign_in_state, base_content = self.check_sign_in_state(entry, base_response, BASE_URL)
        if sign_in_state != SignState.NO_SIGN_IN:
            return

        data = {
            'action': (None, 'new')
        }

        image_hash_response = self._request(entry, 'post', IMAGE_HASH_URL, files=data)
        image_hash_net_state = self.check_net_state(entry, image_hash_response, IMAGE_HASH_URL)
        if image_hash_net_state:
            return
        content = self._decode(image_hash_response)
        image_hash = json.loads(content)['code']

        if image_hash:
            img_url = IMAGE_URL.format(image_hash)
            img_response = self._request(entry, 'get', img_url)
            img_net_state = self.check_net_state(entry, img_response, img_url)
            if img_net_state:
                return
        else:
            entry.fail_with_prefix('Cannot find: image_hash')
            return
        img = Image.open(BytesIO(img_response.content))
        code, img_byte_arr = BaiduOcr.get_ocr_code(img, entry, config)
        if not entry.failed:
            if len(code) == 6:
                data = {
                    'action': (None, 'showup'),
                    'imagehash': (None, image_hash),
                    'imagestring': (None, code)
                }
                response = self._request(entry, 'post', URL, files=data)
                final_state = self.final_check(entry, response, response.request.url)
            if len(code) != 6 or final_state == SignState.WRONG_ANSWER:
                code_file = Path('hdsky.png')
                code_file.write_bytes(img_byte_arr)
                entry.fail_with_prefix('ocr failed: {}, see hdsky.png'.format(code))

    def build_selector(self):
        selector = super(MainClass, self).build_selector()
        self.dict_merge(selector, {
            'details': {
                'hr': None
            }
        })
        return selector
