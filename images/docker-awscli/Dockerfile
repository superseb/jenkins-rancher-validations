FROM alpine:latest

RUN \
	mkdir -p /aws && \
	apk -Uuv add groff less python py-pip curl bash && \
	pip install awscli && \
	apk --purge -v del py-pip && \
	rm /var/cache/apk/*

RUN curl http://s3.amazonaws.com/ec2metadata/ec2-metadata > /usr/bin/ec2metadata
RUN chmod +x /usr/bin/ec2metadata
WORKDIR /aws
