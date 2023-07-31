# Generate Docker image file.

# Run it on latest Amazon Linux 2.
FROM amazonlinux:2023
LABEL maintainer="jcleveng@fas.harvard.edu"

# Python version to install
ENV pythonmajor 3

# Do a bunch of installs, all combined into a single RUN command because it
# dramatically reduces the size of the image file (in this case from 427MB
# down to 128MB).
# 	- run OS security updates.
# 	- add the EPEL yum repo
#		- install python
RUN \
	yum -y update --security; \
	rpm -Uvh http://dl.fedoraproject.org/pub/epel/epel-release-latest-7.noarch.rpm; \
	yum -y install python${pythonmajor}; \
	yum -y install python${pythonmajor}-pip; \
	yum -y install git \
	dnf -y install openssl && \
	yum clean all

# Install Python application and change working directory to it.
COPY src /opt/app
WORKDIR /opt/app


# # Install the Python modules our API application uses.
RUN pip3 install -r requirements.txt

# Needed for boto to be able to find the parameter store
ENV AWS_DEFAULT_REGION us-east-1

# make sure the stack env var is picked up for use in the build
ARG STACK

# Start app.py from our src folder.
ENTRYPOINT [ "python3", "-u", "app.py" ]