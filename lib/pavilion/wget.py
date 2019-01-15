import urllib.parse
import requests
import os
import tempfile


class WGetError(RuntimeError):
    pass


def get(pav_cfg, url, dest):
    """Download the file at the given url and store it at dest. If a file already exists at dest
    it will be overwritten (assuming we have the permissions to do so). Proxies are handled
    automatically based on pav_cfg settings. This is done atomically; the download is saved to an
    intermediate location and then moved.
    :param pav_cfg: The pavilion configuration object.
    :param str url: The url for the file to download.
    :param str dest: The path to where the file will be stored.
    """

    proxy = _get_proxy(pav_cfg, url)

    session = requests.Session()
    session.trust_env = False

    dest_dir = os.path.dirname(os.path.realpath(dest))

    try:
        tmp = tempfile.NamedTemporaryFile(dir=dest_dir)
        with session.get(url, proxy=proxy, stream=True) as response:
            for chunk in response.iter_content(chunk_size=4096):
                tmp.write(chunk)
    except requests.exceptions.RequestException as err:
        # The requests package exceptions are pretty descriptive already.
        raise WGetError(err)
    except (IOError, OSError) as err:
        raise WGetError("Error writing download '{}' to file in '{}': {}"
                        .format(url, dest_dir, err))

    try:
        os.rename(tmp.name, dest)
    except (IOError, OSError) as err:
        raise WGetError("Error moving file from '{}' to final location '{}': {}"
                        .format(url, dest, err))


def get_file_info(pav_cfg, url):
    """Get the header information for the given url.
    :param pav_cfg: The pavilion configuration object
    :param str url: The url we need information on.
    :returns: The http headers for the given url.
    :rtype dict:
    """

    proxy = _get_proxy(pav_cfg, url)

    session = requests.Session()
    session.trust_env = False

    try:
        response = session.head(url, proxy=proxy)
        if 'Content-Length' not in response.headers:
            # Sometimes the first request doesn't return a content length, and you have to do
            # it again.
            response = session.head(url, proxy=proxy)
    except requests.exceptions.RequestException as err:
        raise WGetError(err)

    return response.headers


def _get_proxy(pav_cfg, url):

    parsed_url = urllib.parse.urlparse(url)
    host = '.' + parsed_url.netloc

    for suffix in pav_cfg.no_proxy:
        if host.endswith('.' + suffix):
            return None

    return pav_cfg.proxies
