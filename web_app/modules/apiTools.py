from urllib.parse import urlparse

from flask import Flask, jsonify, request, Response, json
from flask_restful import Api, Resource


valid_img_formats = ['jpg', 'png', 'webp']


def genResponse(ret_json, ret_status):
	return Response(
		response=json.dumps(ret_json),
		status=ret_status,
		mimetype='application/json'
	)


def validate_body_content(list_contents):
	pass


def validateImgUrl(url):
	parsed_url = urlparse(url)
	img_format = parsed_url.path.split('.')[-1]
	
	return img_format.lower() in valid_img_formats


if __name__ == '__main__':
	test_url = 'https://img.freepik.com/fotos-gratis/gatinho-domestico-fofo-senta-na-janela-olhando-para-fora-da-ia-generativa_188544-12519'
	print(validate_url_img(test_url))