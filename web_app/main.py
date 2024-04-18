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


#mongoDb = MongoDb("mongodb://db:27017") dockercompose
mongoDb = MongoDb("mongodb://127.0.0.1:27017")


pretrained_model = InceptionV3(weights="imagenet")


class userCreate(Resource):
	def post(self):
			posted_data = request.get_json()

			user_id = posted_data["username"]
			pwd = posted_data["password"]

			ret_resp = mongoDb.registerUser(user_id, pwd)

			return genResponse(
				ret_json={'msg': ret_resp['msg']},
				ret_status=ret_resp['resp_code'])	


class user(Resource):
		def get(self, user_id):
			posted_data = request.get_json()
			
			pwd = posted_data["password"]

			auth_resp = mongoDb.authUser(user_id, pwd)
			if not auth_resp['auth']:
				return genResponse(
					ret_json={'msg': auth_resp['err_msg']},
					ret_status=auth_resp['resp_code'])

			return genResponse( 
				ret_json={'msg': f'Number of tokens: {mongoDb.getNumTokens(user_id)}'},
				ret_status=200)


		def post(self, user_id):
			posted_data = request.get_json()

			pwd = posted_data["password"]
			new_pwd = posted_data["new_password"]

			auth_resp = mongoDb.authUser(user_id, pwd)
			if not auth_resp['auth']:
				return genResponse(
					ret_json={'msg': auth_resp['err_msg']},
					ret_status=auth_resp['resp_code'])

			ret_resp = mongoDb.updateUserPwd(user_id, pwd, new_pwd)

			return genResponse(
				ret_json={'msg': ret_resp['msg']},
				ret_status=ret_resp['resp_code'])


		def delete(self, user_id):
			posted_data = request.get_json()

			pwd = posted_data["password"]

			auth_resp = mongoDb.authUser(user_id, pwd)
			if not auth_resp['auth']:
				return genResponse(
					ret_json={'msg': auth_resp['err_msg']},
					ret_status=auth_resp['resp_code'])

			ret_resp = mongoDb.deleteUser(user_id, pwd)

			return genResponse(
				ret_json={'msg': ret_resp['msg']},
				ret_status=ret_resp['resp_code'])
	

class classify(Resource):
	def post(self):
		posted_data = request.get_json()

		user_id = posted_data["username"]
		pwd = posted_data["password"]
		url = posted_data["url"]

		if not url or not pwd or not user_id:
			return genResponse(
				ret_json={'msg': "Missing argument."},
				ret_status=400) # 400 Bad Request

		if not validateImgUrl(url):
			return genResponse(
				ret_json={'msg': "Invalid Url"},
				ret_status=415) # 415 Unsupported Media Type

		auth_resp = mongoDb.authUser(user_id, pwd)
		if not auth_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_resp['err_msg']},
				ret_status=auth_resp['resp_code'])

		elif (num_tokens := mongoDb.getNumTokens(user_id)) <= 0:
			return genResponse(
				ret_json={'msg': "Not enough tokens"},
				ret_status=403) # 403 Forbidden

		elif auth_resp['auth'] and num_tokens > 0:
			cached_url_result = mongoDb.getCachedUrlResult(url)
			
			if cached_url_result is not None:
				ret_json = cached_url_result
				ret_json['remaining_tokens'] = num_tokens - 1

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

				ret_json = {str(pred[1]): float(pred[2]) for pred in actual_prediction[0]}
				mongoDb.cacheUrlResult(url, ret_json)

			mongoDb.add2usrTokens(user_id, -1)
			ret_json['remaining_tokens'] = num_tokens - 1 # avoid another call to db

			return genResponse(
				ret_json=ret_json,
				ret_status=200)


class refill(Resource):
	def post(self):
		posted_data = request.get_json()

		user_id = posted_data["username"]
		adm_pwd = posted_data["adm_pwd"]
		refill_amt = int(posted_data["refill"])

		if not isinstance(refill_amt, int):
			return genResponse(
				ret_json={'msg': f"Error, invalid argument '{refill_amt}', expected integer."},
				ret_status=304)

		elif not mongoDb.userExist(user_id):
			return genResponse(
				ret_json={'msg': f"Useramer {user_id} not found."},
				ret_status=400)

		auth_resp_adm = authAdm(user_id, adm_pwd)
		if not auth_resp_adm['auth']:
			return genResponse(
				ret_json={'msg': auth_resp_adm['err_msg']},
				ret_status=auth_resp['resp_code'])

		mongoDb.add2usrTokens(user_id, refill_amt)
		return genResponse(
				ret_json={'msg': f"Refill successful, {refill_amt} tokens added for user {user_id}."},
				ret_status=200)


#create admin route: initial password, remoive cached, promote/demote admin
class rootAdminInitialPassword(Resource):
	def post(self):
		new_pwd = posted_data["new_pwd"]

		'''
		!#!#!#!#!#!#!#!#!#!#!#!#!!$!$!$!$!$!$!$%!%!%!%!%!
		CHECK IF THIS ERROR HANDLING WORKS
		!#!#!#!#!#!#!#!#!#!#!#!#!!$!$!$!$!$!$!$%!%!%!%!%!
		'''
		print(new_pwd)
		if not new_pwd:
			return genResponse(
				ret_json={'msg': "Missing argument."},
				ret_status=400)

		reponse = mongoDb.rootAdmFirstPwd(new_pwd)

		return genResponse(
			ret_json={'msg': response['msg']},
			ret_status=reponse['resp_code'])


class deleteCachedUrl(Resource):
	def post(self):
		url = posted_data["url"]
		adm_id = posted_data["adm_id"]
		adm_pwd = posted_data["adm_pwd"]

		resp_auth_adm = mongoDb.authAdm(adm_id, adm_pwd)
		if not resp_auth_adm['auth']:
			return genResponse(
					ret_json={'msg': resp_auth_adm['msg']},
					ret_status=resp_auth_adm['resp_code'])

		else:
			dlt_resp = mongoDb.deleteCachedUrl(adm_id, adm_pwd)
			return genResponse(ret_json={'msg': dlt_resp['msg']},
								ret_status=dlt_resp['resp_code'])


class promote2adm(Resource):
	def post(self):
		usr_id = posted_data["usr_id"]
		root_adm_pwd = posted_data["adm_pwd"]

		auth_resp = authAdm('root_admin', root_adm_pwd)
		if not auth_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_resp['err_msg']},
				ret_status=auth_resp['resp_code'])
		
		elif auth_resp_adm['auth'] and not mongoDb.isAdm(usr_id):
			resp = mongoDb.promote2adm(usr_id)
			return genResponse(ret_json={'msg': resp['msg']},
								ret_status=resp['resp_code'])


class demoteAdm(Resource):
	def post(self):
		usr_id = posted_data["usr_id"]
		root_adm_pwd = posted_data["adm_pwd"]

		auth_resp = authAdm('root_admin', root_adm_pwd)
		if not auth_resp['auth']:
			return genResponse(
				ret_json={'msg': auth_resp['err_msg']},
				ret_status=auth_resp['resp_code'])
		
		elif auth_resp_adm['auth']:
			resp = mongoDb.demoteAdm(usr_id)
			return genResponse(ret_json={'msg': resp['msg']},
								ret_status=resp['resp_code'])


api.add_resource(userCreate, '/user/create')
api.add_resource(user, '/user/<string:user_id>')
api.add_resource(classify, '/classify/')
api.add_resource(refill, '/admin/refill/')
api.add_resource(rootAdminInitialPassword, '/admin/rootAdmInitialPassword')
api.add_resource(promote2adm, '/admin/promoteToAdmin/<string:usr_id>')
api.add_resource(demoteAdm, '/admin/demoteFromAdmin/<string:usr_id>')
api.add_resource(deleteCachedUrl, '/admin/deleteCachedUrl')


if __name__ == '__main__':
	app.run(host='0.0.0.0', port=5000)