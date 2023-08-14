FROM fluxrm/flux-sched:focal
# docker build -f examples/flux/Dockerfile -t flux-pavilion .
# docker run -it -v $PWD:/code flux-pavilion
# docker run -it flux-pavilion
USER root
ENV PATH=/opt/conda/bin:$PATH
ENV PYTHONPATH $PYTHONPATH:/opt/yaml_config/lib
WORKDIR /code
COPY . /code
# Their setup script wants to make a venv
RUN python3 -m pip install -r /code/requirements.txt && \
    # This isn't an actual python module!
    git clone https://github.com/lanl-preteam/yaml_config /opt/yaml_config

ENV PATH=/code/bin:$PATH
# If you want to develop, you'll need to comment this
# USER fluxuser
