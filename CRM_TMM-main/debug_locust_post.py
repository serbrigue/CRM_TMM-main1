#!/usr/bin/env python3
import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error
import sys

def run(enroll_id='23'):
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    url = f'http://web:8000/talleres/{enroll_id}/'
    print('GET', url)
    try:
        resp = opener.open(url)
        print('GET status', resp.getcode())
        html = resp.read().decode(errors='replace')
        print('\n--- HTML sample (first 1200 chars) ---')
        print(html[:1200])
        token = None
        idx = html.find('name="csrfmiddlewaretoken"')
        if idx == -1:
            idx = html.find("name='csrfmiddlewaretoken'")
        if idx != -1:
            v_idx = html.find('value="', idx)
            if v_idx != -1:
                v_end = html.find('"', v_idx+7)
                token = html[v_idx+7:v_end]
        print('\nCSRF in HTML:', bool(token))
        print('CSRF token:', token[:40] if token else None)
        print('\nCookies:', [(c.name,c.value) for c in cj])
    except Exception as e:
        print('GET error:', repr(e))
        sys.exit(1)

    post_data = {'nombre':'LocustTester','email':'test@example.com','telefono':'+56912345678'}
    headers = {}
    if token:
        headers['X-CSRFToken'] = token
        headers['Referer'] = url
    req = urllib.request.Request(url, data=urllib.parse.urlencode(post_data).encode(), headers=headers)
    print('\n--- POST attempt ---')
    try:
        post = opener.open(req)
        print('POST status', post.getcode())
        body = post.read().decode(errors='replace')
        print('\nPOST body (first 1600 chars):')
        print(body[:1600])
    except urllib.error.HTTPError as e:
        print('POST HTTPError', e.code)
        try:
            print(e.read().decode(errors='replace')[:2000])
        except Exception:
            pass
    except Exception as e:
        print('POST error', repr(e))


def run_with_login(enroll_id='23', username='testuser', password='testpass'):
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    login_url = 'http://web:8000/login/'
    print('Login GET', login_url)
    try:
        r = opener.open(login_url)
        html = r.read().decode(errors='replace')
        token = None
        idx = html.find('name="csrfmiddlewaretoken"')
        if idx == -1:
            idx = html.find("name='csrfmiddlewaretoken'")
        if idx != -1:
            v_idx = html.find('value="', idx)
            if v_idx != -1:
                v_end = html.find('"', v_idx+7)
                token = html[v_idx+7:v_end]
        print('Login CSRF token:', token[:40] if token else None)
        print('Cookies after login GET:', [(c.name,c.value) for c in cj])
    except Exception as e:
        print('Login GET error', repr(e))
        return

    headers = {}
    if token:
        headers['X-CSRFToken'] = token
        headers['Referer'] = login_url
    creds = {'username': username, 'password': password}
    req = urllib.request.Request(login_url, data=urllib.parse.urlencode(creds).encode(), headers=headers)
    print('\nLogin POST')
    try:
        resp = opener.open(req)
        print('Login POST status', getattr(resp, 'getcode', lambda: None)())
    except urllib.error.HTTPError as e:
        print('Login POST HTTPError', e.code)
        try:
            print(e.read().decode(errors='replace')[:1200])
        except Exception:
            pass
        return
    except Exception as e:
        print('Login POST error', repr(e))
        return

    print('Cookies after login POST:', [(c.name,c.value) for c in cj])
    # Now GET enroll page and POST
    print('\nProceeding to enroll flow as logged user')
    enroll_url = f'http://web:8000/talleres/{enroll_id}/'
    try:
        r = opener.open(enroll_url)
        print('Enroll GET status', r.getcode())
        html = r.read().decode(errors='replace')
        print('\n--- Enroll HTML sample (first 800 chars) ---')
        print(html[:800])
        token = None
        idx = html.find('name="csrfmiddlewaretoken"')
        if idx == -1:
            idx = html.find("name='csrfmiddlewaretoken'")
        if idx != -1:
            v_idx = html.find('value="', idx)
            if v_idx != -1:
                v_end = html.find('"', v_idx+7)
                token = html[v_idx+7:v_end]
        print('Enroll CSRF:', bool(token), 'token:', token[:40] if token else None)
        print('Cookies now:', [(c.name,c.value) for c in cj])
    except Exception as e:
        print('Enroll GET error', repr(e))
        return

    post_data = {'nombre':'LocustTester','email':'test@example.com','telefono':'+56912345678'}
    headers = {}
    if token:
        headers['X-CSRFToken'] = token
        headers['Referer'] = enroll_url
    req = urllib.request.Request(enroll_url, data=urllib.parse.urlencode(post_data).encode(), headers=headers)
    print('\n--- Enroll POST attempt ---')
    try:
        post = opener.open(req)
        print('Enroll POST status', post.getcode())
        print(post.read().decode(errors='replace')[:1200])
    except urllib.error.HTTPError as e:
        print('Enroll POST HTTPError', e.code)
        try:
            print(e.read().decode(errors='replace')[:2000])
        except Exception:
            pass
    except Exception as e:
        print('Enroll POST error', repr(e))

if __name__ == '__main__':
    enroll = '23'
    if len(sys.argv) > 1:
        enroll = sys.argv[1]
    run(enroll)
