import numpy as np
import urllib.request
import os

from modules.mongoDbManager import MongoDb
from modules.apiTools import *

from flask import Flask, jsonify, request, Response, json
from flask_restful import Api, Resource

from PIL import Image
from tensorflow.keras.preprocessing.image import img_to_array
from keras.applications import InceptionV3
from keras.applications.inception_v3 import preprocess_input
from keras.applications import imagenet_utils


app = Flask(__name__)
api = Api(app)


mongoDb = MongoDb("mongodb://db:27017") #dockercompose
#mongoDb = MongoDb("mongodb://127.0.0.1:27017") for test in local machine


pretrained_model = InceptionV3(weights="imagenet")


class userCreate(Resource):
	def post(self):
		posted_data = request.get_json()

		expected_content = ["username", "password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400) # 400 Bad Request

		elif body_validation['validation']:
			user_id = posted_data["username"]
			pwd = posted_data["password"]

		ret_resp = mongoDb.registerUser(user_id, pwd)

		return genResponse(
			ret_json={'msg': ret_resp['msg']},
			ret_status=ret_resp['resp_code'])


class user(Resource):
	def get(self, user_id):
		posted_data = request.get_json()
		
		expected_content = ["password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400) # 400 Bad Request

		elif body_validation['validation']:
			pwd = posted_data["password"]

		auth_adm_resp = mongoDb.authUser(user_id, pwd)
		if not auth_adm_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_adm_resp['err_msg']},
				ret_status=auth_adm_resp['resp_code'])

		num_tokens = mongoDb.getNumTokens(user_id)
		return genResponse( 
			ret_json={'msg': f'Number of tokens: {num_tokens}', 'num': num_tokens},
			ret_status=200)


	def post(self, user_id):
		posted_data = request.get_json()

		expected_content = ["password", "new_password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400) # 400 Bad Request
		
		elif body_validation['validation']:
			pwd = posted_data["password"]
			new_pwd = posted_data["new_password"]

		auth_adm_resp = mongoDb.authUser(user_id, pwd)
		if not auth_adm_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_adm_resp['err_msg']},
				ret_status=auth_adm_resp['resp_code'])

		ret_resp = mongoDb.updateUserPwd(user_id, pwd, new_pwd)

		return genResponse(
			ret_json={'msg': ret_resp['msg']},
			ret_status=ret_resp['resp_code'])


	def delete(self, user_id):
		posted_data = request.get_json()

		expected_content = ["password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400) # 400 Bad Request
		
		elif body_validation['validation']:
			pwd = posted_data["password"]

		auth_adm_resp = mongoDb.authUser(user_id, pwd)
		if not auth_adm_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_adm_resp['err_msg']},
				ret_status=auth_adm_resp['resp_code'])

		ret_resp = mongoDb.deleteUser(user_id, pwd)

		return genResponse(
			ret_json={'msg': ret_resp['msg']},
			ret_status=ret_resp['resp_code'])
	

class classify(Resource):
	def post(self):
		posted_data = request.get_json()

		expected_content = ["username", "password", "url"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400) # 400 Bad Request

		elif body_validation['validation']:
			user_id = posted_data["username"]
			pwd = posted_data["password"]
			url = posted_data["url"]

		if not validateImgUrl(url):
			return genResponse(
				ret_json={'msg': "Invalid Url"},
				ret_status=415) # 415 Unsupported Media Type

		auth_adm_resp = mongoDb.authUser(user_id, pwd)
		if not auth_adm_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_adm_resp['err_msg']},
				ret_status=auth_adm_resp['resp_code'])

		elif (num_tokens := mongoDb.getNumTokens(user_id)) <= 0:
			return genResponse(
				ret_json={'msg': "Not enough tokens"},
				ret_status=403) # 403 Forbidden

		elif auth_adm_resp['auth'] and num_tokens > 0:
			cached_url_result = mongoDb.getCachedUrlResult(url)
			
			if cached_url_result is not None:
				ret_json = cached_url_result
				ret_json['remaining_tokens'] = num_tokens - 1
				ret_json['cached_url'] = True

			else:
				urllib.request.urlretrieve(url,"img.jpg")
				img = Image.open("img.jpg")

				#image treatement
				img = img.resize((299, 299))
				img_array = img_to_array(img)
				img_array = np.expand_dims(img_array, axis=0)
				img_array = preprocess_input(img_array)

				#use model
				prediction = pretrained_model.predict(img_array)
				actual_prediction = imagenet_utils.decode_predictions(prediction, top=5)

				predictions = {str(pred[1]): float(pred[2]) for pred in actual_prediction[0]}
				ret_json = {'predictions': predictions}
				mongoDb.cacheUrlResult(url, ret_json)
				ret_json['cached_url'] = False

			mongoDb.add2usrTokens(user_id, -1)
			ret_json['remaining_tokens'] = num_tokens - 1 # avoid another call to db

			return genResponse(
				ret_json=ret_json,
				ret_status=200)


#create admin route: initial password, remoive cached, promote/demote admin
class rootAdminInitialPassword(Resource):
	def post(self):
		posted_data = request.get_json()

		expected_content = ["new_pwd", "initial_password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400) # 400 Bad Request

		elif body_validation['validation']:
			new_pwd = posted_data["new_pwd"]
			initial_pwd = posted_data["initial_password"]

		response = mongoDb.rootAdmFirstPwd(new_pwd, initial_pwd)

		return genResponse(
			ret_json={'msg': response['msg']},
			ret_status=response['resp_code'])


class promote2adm(Resource):
	def post(self):
		posted_data = request.get_json()

		expected_content = ["username", "root_adm_password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400) # 400 Bad Request

		elif body_validation['validation']:
			usr_id = posted_data["username"]
			root_adm_pwd = posted_data["root_adm_password"]

		if mongoDb.isAdm(usr_id):
			return genResponse(ret_json={'msg': f"User {usr_id} is already adm."},
								ret_status=400)

		auth_adm_resp = mongoDb.authAdm('root_admin', root_adm_pwd)
		if not auth_adm_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_adm_resp['err_msg']},
				ret_status=auth_adm_resp['resp_code'])
		
		elif auth_adm_resp['auth']:
			resp = mongoDb.promote2adm(usr_id)
			return genResponse(ret_json={'msg': resp['msg']},
								ret_status=resp['resp_code'])


class demoteAdm(Resource):
	def post(self):
		posted_data = request.get_json()

		expected_content = ["username", "root_adm_password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400)

		elif body_validation['validation']:
			usr_id = posted_data["username"]
			root_adm_pwd = posted_data["root_adm_password"]

		if not mongoDb.isAdm(usr_id):
			return genResponse(ret_json={'msg': f"User {usr_id} is not adm."},
								ret_status=404)

		auth_adm_resp = mongoDb.authAdm('root_admin', root_adm_pwd)		
		if not auth_adm_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_adm_resp['err_msg']},
				ret_status=auth_adm_resp['resp_code'])

		elif auth_adm_resp['auth']:
			resp = mongoDb.demoteAdm(usr_id)
			return genResponse(ret_json={'msg': resp['msg']},
								ret_status=resp['resp_code'])


class refill(Resource):
	def post(self, admin_id):
		posted_data = request.get_json()

		expected_content = ["username", "adm_password", "refill"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400)

		elif body_validation['validation']:
			user_id = posted_data["username"]
			adm_pwd = posted_data["adm_password"]
			refill_amt = posted_data["refill"]

		if not isinstance(refill_amt, int):
			return genResponse(
				ret_json={'msg': f"Error: invalid argument \'{refill_amt}\', expected integer."},
				ret_status=400)

		elif not mongoDb.userExist(user_id):
			return genResponse(
				ret_json={'msg': f"Useramer \'{user_id}\' not found."},
				ret_status=400)

		auth_adm_resp = mongoDb.authAdm(admin_id, adm_pwd)
		if not auth_adm_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_adm_resp['err_msg']},
				ret_status=auth_adm_resp['resp_code'])

		mongoDb.add2usrTokens(user_id, refill_amt)
		return genResponse(
				ret_json={'msg': f"Refill successful, {refill_amt} tokens added for user {user_id}."},
				ret_status=200)


class deleteCachedUrl(Resource):
	def post(self, admin_id):
		posted_data = request.get_json()

		expected_content = ["url", "adm_password"]
		body_validation = validateBodyContent(posted_data, expected_content)
		if not body_validation['validation']:
			return genResponse(ret_json={'msg': body_validation['msg']},ret_status=400)

		elif body_validation['validation']:
			url = posted_data["url"]
			adm_pwd = posted_data["adm_password"]

		auth_adm_resp = mongoDb.authAdm(admin_id, adm_pwd)
		if not auth_adm_resp['auth']:
			return genResponse(
					ret_json={'msg': auth_adm_resp['err_msg']},
					ret_status=auth_adm_resp['resp_code'])

		else:
			dlt_resp = mongoDb.deleteCachedUrl(url)
			return genResponse(ret_json={'msg': dlt_resp['msg']},
								ret_status=dlt_resp['resp_code'])


api.add_resource(userCreate, '/user/create')
api.add_resource(user, '/user/<string:user_id>')
api.add_resource(classify, '/classify')
api.add_resource(rootAdminInitialPassword, '/admin/rootAdmInitialPassword')
api.add_resource(promote2adm, '/admin/promoteToAdmin')
api.add_resource(demoteAdm, '/admin/demoteFromAdmin')
api.add_resource(refill, '/admin/<string:admin_id>/refill')
api.add_resource(deleteCachedUrl, '/admin/<string:admin_id>/deleteCachedUrl')


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000)