import hashlib
import pytest
from tools.adapt_sun_delivery_metadata import normalize_render


def test_old_final_sha_cannot_authorize_new_film(tmp_path):
    movie=tmp_path/'film.mp4';movie.write_bytes(b'new master')
    with pytest.raises(ValueError,match='current actual film'):
        normalize_render(movie,{}, {'status':'PASS','video_sha256':'old','video_bytes':10})


def test_unapproved_matching_film_still_rejected(tmp_path):
    movie=tmp_path/'film.mp4';movie.write_bytes(b'new master')
    q={'status':'PENDING','video_sha256':hashlib.sha256(movie.read_bytes()).hexdigest(),'video_bytes':movie.stat().st_size}
    with pytest.raises(ValueError,match='must PASS'):
        normalize_render(movie,{},q)
