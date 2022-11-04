# To enable ssh & remote debugging on app service change the base image to the one below
# FROM mcr.microsoft.com/azure-functions/python:4-python3.9-appservice
FROM mcr.microsoft.com/azure-functions/python:4-python3.9

ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true

RUN apt-get update && apt-get install -y \
    #gcc \
    git \
    #unzip \
    #python3-dev \
    #libgl1-mesa-glx \
    libgdal-dev \
    g++ \
 && rm -rf /var/lib/apt/lists/*

RUN pip install Cython==0.29.30 numpy==1.22.4

COPY requirements.txt /
RUN pip install -r requirements.txt

COPY . /home/site/wwwroot