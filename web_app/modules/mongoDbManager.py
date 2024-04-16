import bcrypt

from datetime import datetime, timedelta
from pymongo import MongoClient

# to avoid having to do any external configuration in db
admin_init_pwd = 'pwd1235'


def check_enc_pwds(passed_pwd, stored_hspwd):
	if bcrypt.hashpw(passed_pwd.encode('utf8'), stored_hspwd) == stored_hspwd:
		return True
	return False


class MongoDb:
	def __init__(self, db_url):
		self.client = MongoClient(db_url)
		self.db = self.client.imgClassifier_db
		
		self.users_col = self.db["users"]
		self.cached_urls_col = self.db["cached_urls"]
		self.admin_col = self.db["admin"]

		if self.admin_col.find_one({"user_id": 'root_admin'}) == None:
			self.admin_col.insert_one({
				"user_id": 'root_admin',
				"password": admin_init_pwd,
				"initial_pwd": True
			})	


	def __del__(self):
		self.client.close()


	def registerUser(self, user_id, user_pwd):
		if self.userExist(user_id):
			return {'msg': "Useramer already in use.", 'resp_code': 301}

		hashed_pwd = bcrypt.hashpw(user_pwd.encode('utf8'), bcrypt.gensalt())
		obj_id = self.users_col.insert_one({
			"user_id": user_id,
			"password": hashed_pwd,
			"tokens": 3
		})

		if obj_id == None:
			return {'msg': "Internal Server Error", 'resp_code': 500}

		return {'msg': f"User '{user_id}' registered successfully", 'resp_code': 200}


	def deleteUser(self, usr_id, usr_pwd):
		auth_resp = self.authUser(usr_id, usr_pwd)
		if not auth_resp['auth']:
			return auth_resp

		else:
			if self.users_col.delete_one({"user_id": user_id}) is not None:
				return {'msg': f"User {usr_id} deleted successfully.", 'resp_code': 200}


	def updateUserPwd(self, usr_id, usr_pwd, new_pwd):
		auth_resp = self.authUser(usr_id, usr_pwd)
		if not auth_resp['auth']:
			return auth_resp

		first_update = (last_updt := self.users_col.find_one({"user_id": usr_id}, 
			{"_id":0, "last_modified":1}).get("last_modified")) is None # important to use '.get' as key could not exist

		one_day = timedelta(days=1)
		if not first_update and (time_since_last_update := datetime.now() - last_updt) < one_day:
			hours_2_valid_2_update = one_day - time_since_last_update
			return {'msg': f"User {usr_id} need to wait {hours_2_valid_2_update} before allowed to another update.", 
					'resp_code': 405}

		self.users_col.update_one({"user_id": usr_id},
			{"$set": {
				"password": new_pwd,
				"last_modified": datetime.now()
			}}
		)

		return {'msg': f"password updated successfully.", 'resp_code': 200}


	def userExist(self, user_id):
		if self.users_col.find_one({"user_id": user_id}) is not None:
			return True
		return False


	def authUser(self, user_id, usr_pwd):
		if not self.userExist(user_id):
			return {'err_msg': "User not registered", 'auth': False, 'resp_code': 404}

		else:
			stored_hspwd = self.users_col.find_one({"user_id": user_id}, {"_id": 0, "password": 1})["password"]

			if check_enc_pwds(passed_pwd=usr_pwd, stored_hspwd=stored_hspwd):
				return {'err_msg': None, 'auth': True, 'resp_code': 200}
			else:
				return {'err_msg': "Invalid password", 'auth': False, 'resp_code': 405}


	def getNumTokens(self, user_id):
		return int(self.users_col.find_one({"user_id": user_id}, {"_id":0, "tokens":1}))["tokens"]


	def add2usrTokens(self, user_id, num_add):
		self.users_col.update_one({"user_id": user_id}, 
			{"$inc": {"tokens": int(num_add)}}
		)
	

	def isAdm(self, user_id):
		if self.adm_col.find_one({"user_id": user_id}) is not None:
			return True
		return False


	def authAdm(self, user_id, adm_pwd):
		is_adm = True if self.adm_col.find_one({"user_id": user_id}) is not None else False
		if not is_adm:
			return {'resp_code': 403, 'auth': False, 'err_msg': "User not registered as admin"}
		
		hs_stored_pwd = self.adm_col.find_one({"user_id": user_id}, {"_id": 0, "password": 1})["password"]
		if hs_stored_pwd == admin_init_pwd:
			return {'resp_code': 401, 'auth': False, 'err_msg': "Invalid: initial admin password"}

		elif check_enc_pwds(adm_pwd, hs_stored_pwd):
			return {'resp_code': 200, 'auth': True, 'err_msg': None}

		else:
			return {'resp_code': 401, 'auth': False, 'err_msg': "Invalid password"}


	# meant only for root adm
	def rootAdmFirstPwd(self, new_pwd):
		stored_pwd = self.admin_col.find_one({"user_id": 'root_admin'}, {"_id": 0, "password": 1})
		if stored_pwd == admin_init_pwd:
			hashed_pwd = bcrypt.hashpw(new_pwd.encode('utf8'), bcrypt.gensalt())
			self.admin_col.update_one({"user_id": 'root_admin'},
				{"$set": {"password": hashed_pwd}}
			)
			return {'resp_code': 200, 'msg': "Admin password updated successfully."}
		else:
			return {'resp_code': 403, 'msg': "Admin initial password already altered."}


	def promote2adm(self, user_id):
		if not self.userExist(user_id):
			return {'resp_code': 400, 'msg': f"User {user_id} not found."}

		else:
			self.admin_col.insert_one({"user_id": 'user_id',
										"usr_pwd": self.users_col.find_one({"user_id": user_id})["password"]
			})
			return {'resp_code': 200, 'msg': f"User {user_id} promoted to admin successfully."}


	def demoteAdm(self, user_id):
		if not self.userExist(user_id):
			return {'resp_code': 400, 'msg': f"User {user_id} not found."}

		else:
			self.admin_col.delete_one({"user_id": user_id})
			return {'resp_code': 200, 'msg': f"Removed user '{user_id}' admin status successfully."}


	def getCachedUrlResult(self, url):
		predictions = self.cached_urls_col.find_one({"url": url}, {"_id": 0, "predictions": 1})
		if found_url == None:
			return None
		else:
			return predictions


	def cacheUrlResult(self, url, predictions):
		self.cached_urls_col.insert_one({
				"url": url,
				"cached_datetime": datetime.now(),
				"predictions": {predictions}
			})


	def deleteCachedUrl(self, url):
		if self.cached_urls_col.find_one({"url": url}) is not None:
			self.cached_urls_col.delete_one({"url": url})
			return {'resp_code': 200, 'msg': f"Removed url '{url}' from cached urls."}

		else:
			return {'resp_code': 404, 'msg': f"Url passed not cached."}



if __name__ == '__main__':
	# execute debug comands here
	mongoDb = MongoDb("mongodb://127.0.0.1:27017")
	print(mongoDb.db.list_collection_names())
	del mongoDb	
