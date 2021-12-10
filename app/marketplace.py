#!/usr/bin/python

import json
import logging
import os
import sys
import threading
from datetime import datetime
from decimal import Decimal
from time import sleep

import boto3
import pytz
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


BOTO3_METERING_MARKETPLACE_CLIENT = 'meteringmarketplace'


class MeterUsageIntegration:

    try:
        _SEND_DIMENSIONS_AFTER = int(os.getenv("SEND_DIMENSIONS_AFTER", default=3600))
    except ValueError:
        _SEND_DIMENSIONS_AFTER = 3600

    # Initializes the integration and starts a thread to send the metering
    # information to AWS Marketplace
    def __init__(self,
                 region_name,
                 product_code,
                 max_send_stop=2,
                 max_send_warning=1):
        self._product_code = product_code
        self._max_send_stop = max_send_stop
        self._max_send_warning = max_send_warning
        self.state = State(max_send_stop, max_send_warning,
                           self._SEND_DIMENSIONS_AFTER)
        self._mms_client = boto3.client(BOTO3_METERING_MARKETPLACE_CLIENT,
                                        region_name=region_name)
        self._initializing = True
        try:
            self._check_connectivity_and_dimensions()
        except ClientError as err:
            self.state.type = "init"
            self.state.add_error(err)
            logger.error(err)
        except:
            self.state.type = "init"
            self.state.add(f"{sys.exc_info()[1]}")
            logger.error((f"{sys.exc_info()[1]}"))

        t = threading.Thread(target=self.run)
        t.start()

    def run(self):
        logger.info("Initializing")
        if self.state.type != "init":
            while True:
                self.meter_usages()
                self.update_state()
                if self.state.type == "stop":
                    message = f"The usage couldn't be sent after {self._max_send_stop } tries. Please check that your product has a way to reach the internet."
                    self.state.add(message)
                    logger.error(message)
                logger.info("Going to sleep")
                sleep(self._SEND_DIMENSIONS_AFTER)

    def get_consumption(self):
        """ Returns all the dimensions from the AAP Controller unique host table """
        dim_timestamp = datetime.utcnow().timestamp()
        dim_timestamp_int = int(dim_timestamp)
        dim_datetime = datetime.fromtimestamp(dim_timestamp).isoformat()
        return {
            "dimensions":[
                {
                    "name": "aap-unique-hosts",
                    "quantity": 10,
                    "timestamp": dim_timestamp_int,
                    "datetime": dim_datetime
                }
            ]
        }

    def get_state(self):
        """ Returns the state """
        return {"state": self.state}

    def meter_usages(self, dry_run=False):
        """ Obtain unique host count and sends it to Marketplace Metering Service (MMS) using the meter_usage method. """
        logger.info(f"meter_usages: dry_run={dry_run}")
        responses = []
        for d in self.get_consumption().get("dimensions", []):
            # If you call meter_usage at start time with 0 as quantity,
            # you won't be able to send another a different quantity for the first hour.
            # Dimensions can only be reported once per hour.
            # We are avoiding this problem here
            if (dry_run):
                responses += [self._meter_usage(dimension=d, dry_run=dry_run)]
            else:
                if not (self._initializing and d.get("quantity", 0) == 0):
                    responses += [
                        self._meter_usage(dimension=d, dry_run=dry_run)
                    ]
                if (self._initializing):
                    logger.info(f"setting _initializing to False")
                    self._initializing = False
        return responses

    def get_status(self):
        """Gets the state of the integration component and the consumption (number of unique hosts) that hasn't been sent to the metering service yet"""
        return {
            "version": "1.0.0",
            "consumption": self.get_consumption(),
            "state": self.get_state()
        }

    def update_state(self):
        get_latest_dimensions = self.get_consumption().get("dimensions", [])
        for d in get_latest_dimensions:
            if d.get("timestamp"):
                self.state.update_type(d.get("timestamp"))
                break


    def _check_connectivity_and_dimensions(self):
        """ Checks the connectivity and the dimensions given sending a dry_run call to the Marketplace Metering Service """
        self.meter_usages(dry_run=True)

    # Send the given dimension and quantity to Marketplace Metering Serverice
    # using the meter_usage method. If the dimension is sent successfully,
    # the quantity for the dimension is reset to 0 in the DB
    # (Only if dry_run is false)
    def _meter_usage(self, dimension, dry_run=False):
        logger.info(f"_metering_usage:  {dimension} ")

        utc_now = datetime.utcnow()
        try:
            # response = self._mms_client.meter_usage(
            #     ProductCode=self._product_code,
            #     Timestamp=utc_now,
            #     UsageDimension=dimension.get("name"),
            #     UsageQuantity=int(dimension.get("quantity")),
            #     DryRun=dry_run)
            print(f"ProductCode: {self._product_code}, Timestamp:{utc_now}, UsageDimension: {dimension.get('name')}, UsageQuantity: {int(dimension.get('quantity'))}")
            response = {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200
                }
            }
            status_code = response["ResponseMetadata"]["HTTPStatusCode"]
            if (not dry_run and status_code == 200):
                self.state.discard_dimension_errors(dimension.get("name"))
            return response

        except ClientError as err:
            if (dry_run):
                raise
            self.state.add_error(err)
            logger.error(err)
        except:
            if (dry_run):
                raise
            self.state.add(f"{sys.exc_info()[1]}")
            logger.error((f"{sys.exc_info()[1]}"))


class State():
    def __init__(self,
                 max_send_stop,
                 max_send_warning,
                 send_usage_after,
                 detail=None):
        self.max_send_stop = max_send_stop
        self.max_send_warning = max_send_warning
        if detail is None:
            detail = set()
        self.details = detail
        self.type = ""
        self._send_usage_after = send_usage_after

    def update_type(self, max_timestamp):
        if self.type != "init":
            utcnow = datetime.utcnow().timestamp()
            if max_timestamp <= (utcnow -
                                 self.max_send_stop * self._send_usage_after):
                self.type = "stop"
            elif max_timestamp <= (
                    utcnow - self.max_send_warning * self._send_usage_after):
                self.type = "warning"
            else:
                self.type = ""
                self.details = set()

    def add(self, detail):
        self.details.add(detail)

    def value(self):
        return (len(self.details) > 0)

    def add_error(self, error):
        self.add(error.response["Error"]["Code"] + ": " +
                 error.response["Error"]["Message"])

    def discard_dimension_errors(self, dimension_name):
        for detail in self.details.copy():
            if (f"usageDimension: {dimension_name}" in detail):
                self.details.discard(detail)
        if (len(self.details) == 0):
            self.type = ""



mui  = MeterUsageIntegration(region_name="us-east-1", product_code="aap")