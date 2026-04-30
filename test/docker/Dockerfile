# Dockerfile for running Pavilion unit tests in a Linux container
# Based on the CI configuration in .github/workflows/unittests.yml

ARG PYTHON_VERSION=3.6
FROM python:${PYTHON_VERSION}

LABEL description="Pavilion unit test runner"

WORKDIR /pavilion

# Copy the entire project
COPY . .

# Install Python dependencies
RUN pwd && ls && pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r test/requirements.txt && \
    pip install --no-cache-dir -r docs/requirements.txt

# Setup Spack
RUN ./test/utils/spack_setup test

# Run tests by default
CMD ["./test/run_tests"]
