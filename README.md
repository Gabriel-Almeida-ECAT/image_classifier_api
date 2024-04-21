## Image Classification API

* API for classification of images via InceptionV3 pre trained model

* Designed around a user/admin system where users have limited use of the api

* Reference project for integration of Python-Flask api, mongodb and docker-compose

---

## Main Comands:

# To initialize docker compose:

* In same folder of the docker-compose.yaml file:
	- sudo docker compose up


# To stop running services:

- just press 'ctrl+c' in the terminal where the docker compose where started


# To Rebuild a service:

* See the service name in the docker-compose.yml file
    - sudo docker build {service_name}

# To acces mongoDb in running docker:

* With the service runnig, open another terminal and do the following commands:
	- sudo docker exec -it image_classifier_api-db-1 sh
	- mongo