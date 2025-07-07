import os
import sys
import json

# Add path to project directory containing MAU_Duyuru.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'MAU Duyuru')))

from MAU_Duyuru import MAUDuyuruTakipci


def test_parse_announcements_basic():
    tracker = MAUDuyuruTakipci()
    html = '''
    <div class="page-announcement-list">
        <div class="item">
            <a href="/link1"></a>
            <div class="has-title">First Announcement</div>
        </div>
        <div class="item">
            <a href="/link2"></a>
            <div class="has-title">Second Announcement</div>
        </div>
    </div>'''
    result = tracker.parse_announcements(html)
    expected = [
        {'title': 'First Announcement', 'link': tracker.base_url + '/link1'},
        {'title': 'Second Announcement', 'link': tracker.base_url + '/link2'}
    ]
    assert result == expected
