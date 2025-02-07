# Flask API in Docker

This is a Flask-based API that runs inside a Docker container. Below are the instructions to build, run, and use the API.

## Requirements

- Docker installed on your machine.

## Setup

Follow these steps to get the API running inside a Docker container.

### 1. Clone or download the project

Clone the repository to your local machine or download the files (`app.py`, `requirements.txt`, and `Dockerfile`).

### 2. Build the Docker Image

Navigate to the project directory and run the following command to build the Docker image: 

docker build -t questions-api .

This will create a Docker image named `questions-api`.

### 3. Run the Docker Container

After the image is built, run the container with the following command:

docker run -p 5000:5000 questions-api

This will start the Flask API in a Docker container and map port `5000` from the container to your local machine.

### 4. Access the API

You can access the API by opening your browser or making requests to:

http://localhost:5000

Make sure to update the URL if you have defined specific routes in your API.

## Usage Example

Once the API is running, you can call the `/categories` endpoint.

### Example:

Example provided in usage_test.py

```
python usage_test.py
```


### 5. Stopping the Container

To stop the container, press `Ctrl+C` in the terminal where the container is running. Alternatively, you can stop the container with the following command:

docker ps  # Find the container ID
docker stop <container_id>

### Troubleshooting

- Ensure that Docker is installed and running on your machine.
- Ensure that the required ports (5000) are available and not in use by other processes.
- If you encounter any issues with dependencies, check the `requirements.txt` file for any missing packages and update as needed.

### License

This project is licensed under the MIT License.
