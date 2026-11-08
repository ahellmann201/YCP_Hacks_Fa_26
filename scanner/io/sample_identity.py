import hashlib


def photo_fingerprint(images):
    hashes=[image.get('sha256') for image in images]
    if not hashes or any(not value for value in hashes):
        return None
    return hashlib.sha256('\n'.join(sorted(hashes)).encode()).hexdigest()
