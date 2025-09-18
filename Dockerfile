# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install Python libraries
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Define the command to run the app
# This makes the app accessible from outside the container on the specified port
CMD ["streamlit", "run", "gantt_line.py", "--server.port=8501", "--server.address=0.0.0.0"]
