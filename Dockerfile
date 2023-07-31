# Generate Docker image file.

# Run it on latest Amazon Linux 2.
FROM amazonlinux:2023
LABEL maintainer="jcleveng@fas.harvard.edu"

# Python version to install
ENV PYTHON_MAJOR_VERSION 3
ENV PYTHON_MINOR_VERSION 11
ENV PYTHON_VERSION ${PYTHON_MAJOR_VERSION}.${PYTHON_MINOR_VERSION}

# Do a bunch of installs, all combined into a single RUN command because it
# dramatically reduces the size of the image file (in this case from 427MB
# down to 128MB).
# 	- run OS security updates.
# 	- add the EPEL yum repo
#		- install python
RUN \
	dnf -y update --security && \
	dnf -y install openssl && \
	dnf -y install shadow-utils && \
	# Python and pip installation
	dnf -y install python${PYTHON_VERSION} && \
	dnf -y install python${PYTHON_VERSION}-pip && \
	# Required for cx_Oracle wheel to build
	dnf -y install gcc python${PYTHON_VERSION}-devel && \
	# Required for the Oracle client to execute
	dnf -y install libnsl && \
	dnf -y install git && \
	# Cleanup
	dnf clean all && \
	rm -rf /var/cache/dnf


# Install Python application and change working directory to it.
COPY src /opt/app
WORKDIR /opt/app


# # Install the Python modules our API application uses.
RUN python${PYTHON_VERSION} -m pip install --user --no-cache-dir -r requirements.txt

# Needed for boto to be able to find the parameter store
ENV AWS_DEFAULT_REGION us-east-1

# make sure the stack env var is picked up for use in the build
ARG STACK

# Start app.py from our src folder.
ENTRYPOINT [ "python3", "-u", "app.py" ]