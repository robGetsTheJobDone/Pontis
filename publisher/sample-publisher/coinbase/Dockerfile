ARG PONTIS_PUBLISHER_BASE_IMAGE_TAG=0.5.5
FROM 42labs/pontis-publisher:$PONTIS_PUBLISHER_BASE_IMAGE_TAG

ARG PUBLISHER_PREFIX="pontis"

COPY fetch-and-publish.py ./fetch-and-publish.py
CMD python fetch-and-publish.py
