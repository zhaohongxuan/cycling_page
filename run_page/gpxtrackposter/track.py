"""Create and maintain info about a given activity track (corresponding to one GPX file)."""
# Copyright 2016-2019 Florian Pigorsch & Contributors. All rights reserved.
#
# Use of this source code is governed by a MIT-style
# license that can be found in the LICENSE file.

import datetime
import json
import os
from collections import namedtuple

import gpxpy as mod_gpxpy
import polyline
import s2sphere as s2
from fit_tool.fit_file import FitFile
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.device_info_message import DeviceInfoMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.messages.software_message import SoftwareMessage
from fit_tool.profile.profile_type import Sport
from polyline_processor import filter_out
from rich import print
from tcxreader.tcxreader import TCXReader

from .exceptions import TrackLoadError
from .utils import parse_datetime_to_local

start_point = namedtuple("start_point", "lat lon")
run_map = namedtuple("polyline", "summary_polyline")

IGNORE_BEFORE_SAVING = os.getenv("IGNORE_BEFORE_SAVING", False)


class Track:
    def __init__(self):
        self.file_names = []
        self.polylines = []
        self.polyline_str = ""
        self.start_time = None
        self.end_time = None
        self.start_time_local = None
        self.end_time_local = None
        self.length = 0
        self.special = False
        self.average_heartrate = None
        self.moving_dict = {}
        self.run_id = 0
        self.start_latlng = []
        self.type = ""
        self.source = ""
        self.name = ""
        self.source = ""
        self.name = ""

    def load_gpx(self, file_name):
        try:
            self.file_names = [os.path.basename(file_name)]
            # Handle empty gpx files
            # (for example, treadmill runs pulled via garmin-connect-export)
            if os.path.getsize(file_name) == 0:
                raise TrackLoadError("Empty GPX file")
            with open(file_name, "rb") as file:
                self._load_gpx_data(mod_gpxpy.parse(file))
        except Exception as e:
            print(
                f"Something went wrong when loading GPX. for file {self.file_names[0]}, we just ignore this file and continue"
            )
            print(str(e))
            pass

    def load_tcx(self, file_name):
        try:
            self.file_names = [os.path.basename(file_name)]
            # Handle empty tcx files
            # (for example, treadmill runs pulled via garmin-connect-export)
            tcx = TCXReader()
            if os.path.getsize(file_name) == 0:
                raise TrackLoadError("Empty TCX file")
            self._load_tcx_data(tcx.read(file_name), file_name=file_name)
        except Exception as e:
            print(
                f"Something went wrong when loading TCX. for file {self.file_names[0]}, we just ignore this file and continue"
            )
            print(str(e))

    def load_fit(self, file_name):
        try:
            self.file_names = [os.path.basename(file_name)]
            # Handle empty fit files
            # (for example, treadmill runs pulled via garmin-connect-export)
            if os.path.getsize(file_name) == 0:
                raise TrackLoadError("Empty FIT file")

            fit = FitFile.from_file(file_name)
            self._load_fit_data(fit)
        except Exception as e:
            print(
                f"Something went wrong when loading FIT. for file {self.file_names[0]}, we just ignore this file and continue"
            )
            print(str(e))

    def load_from_db(self, activity):
        # use strava as file name
        self.file_names = [str(activity.run_id)]
        start_time = datetime.datetime.strptime(
            activity.start_date_local, "%Y-%m-%d %H:%M:%S"
        )
        self.start_time_local = start_time
        self.end_time = start_time + activity.elapsed_time
        self.length = float(activity.distance)
        if not IGNORE_BEFORE_SAVING:
            summary_polyline = filter_out(activity.summary_polyline)
        polyline_data = polyline.decode(summary_polyline) if summary_polyline else []
        self.polylines = [[s2.LatLng.from_degrees(p[0], p[1]) for p in polyline_data]]
        self.run_id = activity.run_id

    def bbox(self):
        """Compute the smallest rectangle that contains the entire track (border box)."""
        bbox = s2.LatLngRect()
        for line in self.polylines:
            for latlng in line:
                bbox = bbox.union(s2.LatLngRect.from_point(latlng.normalized()))
        return bbox

    def _load_gpx_data(self, gpx):
        self.start_time, self.end_time = gpx.get_time_bounds()
        # use timestamp as id
        self.run_id = int(datetime.datetime.timestamp(self.start_time) * 1000)
        self.start_time_local, self.end_time_local = parse_datetime_to_local(
            self.start_time, self.end_time, gpx
        )
        if self.start_time is None:
            raise TrackLoadError("Track has no start time.")
        if self.end_time is None:
            raise TrackLoadError("Track has no end time.")
        self.length = gpx.length_2d()
        if self.length == 0:
            raise TrackLoadError("Track is empty.")
        gpx.simplify()
        polyline_container = []
        heart_rate_list = []
        # determinate type
        if gpx.tracks[0].type:
            self.type = gpx.tracks[0].type
        # determinate source
        if gpx.creator:
            self.source = gpx.creator
        elif gpx.tracks[0].source:
            self.source = gpx.tracks[0].source
        if self.source == "xingzhe":
            self.start_time_local = self.start_time
            self.run_id = gpx.tracks[0].number
        # determinate name
        if gpx.name:
            self.name = gpx.name
        elif gpx.tracks[0].name:
            self.name = gpx.tracks[0].name
        else:
            self.name = self.type + " from " + self.source

        for t in gpx.tracks:
            for s in t.segments:
                try:
                    heart_rate_list.extend(
                        [
                            int(p.extensions[0].getchildren()[0].text)
                            for p in s.points
                            if p.extensions
                        ]
                    )
                except:
                    pass
                line = [
                    s2.LatLng.from_degrees(p.latitude, p.longitude) for p in s.points
                ]
                self.polylines.append(line)
                polyline_container.extend([[p.latitude, p.longitude] for p in s.points])
                self.polyline_container = polyline_container
        # get start point
        try:
            self.start_latlng = start_point(*polyline_container[0])
        except:
            pass
        self.polyline_str = polyline.encode(polyline_container)
        self.average_heartrate = (
            sum(heart_rate_list) / len(heart_rate_list) if heart_rate_list else None
        )
        self.moving_dict = self._get_moving_data(gpx)

    def _load_fit_data(self, fit: FitFile):
        _polylines = []
        self.polyline_container = []

        for record in fit.records:
            message = record.message

            if isinstance(message, RecordMessage):
                if message.position_lat and message.position_long:
                    _polylines.append(
                        s2.LatLng.from_degrees(
                            message.position_lat, message.position_long
                        )
                    )
                    self.polyline_container.append(
                        [message.position_lat, message.position_long]
                    )
            elif isinstance(message, SessionMessage):
                self.start_time = datetime.datetime.utcfromtimestamp(
                    message.start_time / 1000
                )
                self.run_id = message.start_time
                self.end_time = datetime.datetime.utcfromtimestamp(
                    (message.start_time + message.total_elapsed_time * 1000) / 1000
                )
                self.length = message.total_distance
                self.average_heartrate = (
                    message.avg_heart_rate if message.avg_heart_rate != 0 else None
                )
                self.type = Sport(message.sport).name.lower()

                # moving_dict
                self.moving_dict["distance"] = message.total_distance
                self.moving_dict["moving_time"] = datetime.timedelta(
                    seconds=message.total_moving_time
                    if message.total_moving_time
                    else message.total_timer_time
                )
                self.moving_dict["elapsed_time"] = datetime.timedelta(
                    seconds=message.total_elapsed_time
                )
                self.moving_dict["average_speed"] = (
                    message.enhanced_avg_speed
                    if message.enhanced_avg_speed
                    else message.avg_speed
                )

        self.start_time_local, self.end_time_local = parse_datetime_to_local(
            self.start_time, self.end_time, self.polyline_container[0]
        )
        self.start_latlng = start_point(*self.polyline_container[0])
        self.polylines.append(_polylines)
        self.polyline_str = polyline.encode(self.polyline_container)

    def append(self, other):
        """Append other track to self."""
        self.end_time = other.end_time
        self.length += other.length
        # TODO maybe a better way
        try:
            self.moving_dict["distance"] += other.moving_dict["distance"]
            self.moving_dict["moving_time"] += other.moving_dict["moving_time"]
            self.moving_dict["elapsed_time"] += other.moving_dict["elapsed_time"]
            self.polyline_container.extend(other.polyline_container)
            self.polyline_str = polyline.encode(self.polyline_container)
            self.moving_dict["average_speed"] = (
                self.moving_dict["distance"]
                / self.moving_dict["moving_time"].total_seconds()
            )
            self.file_names.extend(other.file_names)
            self.special = self.special or other.special
        except:
            print(
                f"something wrong append this {self.end_time},in files {str(self.file_names)}"
            )
            pass

    def load_cache(self, cache_file_name):
        try:
            with open(cache_file_name) as data_file:
                data = json.load(data_file)
                self.start_time = datetime.datetime.strptime(
                    data["start"], "%Y-%m-%d %H:%M:%S"
                )
                self.end_time = datetime.datetime.strptime(
                    data["end"], "%Y-%m-%d %H:%M:%S"
                )
                self.start_time_local = datetime.datetime.strptime(
                    data["start_local"], "%Y-%m-%d %H:%M:%S"
                )
                self.end_time_local = datetime.datetime.strptime(
                    data["end_local"], "%Y-%m-%d %H:%M:%S"
                )
                self.length = float(data["length"])
                self.polylines = []
                for data_line in data["segments"]:
                    self.polylines.append(
                        [
                            s2.LatLng.from_degrees(float(d["lat"]), float(d["lng"]))
                            for d in data_line
                        ]
                    )
        except Exception as e:
            raise TrackLoadError("Failed to load track data from cache.") from e

    def store_cache(self, cache_file_name):
        """Cache the current track"""
        dir_name = os.path.dirname(cache_file_name)
        if not os.path.isdir(dir_name):
            os.makedirs(dir_name)
        with open(cache_file_name, "w") as json_file:
            lines_data = []
            for line in self.polylines:
                lines_data.append(
                    [
                        {"lat": latlng.lat().degrees, "lng": latlng.lng().degrees}
                        for latlng in line
                    ]
                )
            json.dump(
                {
                    "start": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "end": self.end_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "start_local": self.start_time_local.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_local": self.end_time_local.strftime("%Y-%m-%d %H:%M:%S"),
                    "length": self.length,
                    "segments": lines_data,
                },
                json_file,
            )

    @staticmethod
    def _get_moving_data(gpx):
        moving_data = gpx.get_moving_data()
        return {
            "distance": moving_data.moving_distance,
            "moving_time": datetime.timedelta(seconds=moving_data.moving_time),
            "elapsed_time": datetime.timedelta(
                seconds=(moving_data.moving_time + moving_data.stopped_time)
            ),
            "average_speed": moving_data.moving_distance / moving_data.moving_time
            if moving_data.moving_time
            else 0,
        }

    def to_namedtuple(self):
        d = {
            "id": self.run_id,
            "name": self.name,
            "type": self.type,
            "start_date": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end": self.end_time.strftime("%Y-%m-%d %H:%M:%S"),
            "start_date_local": self.start_time_local.strftime("%Y-%m-%d %H:%M:%S"),
            "end_local": self.end_time_local.strftime("%Y-%m-%d %H:%M:%S"),
            "length": self.length,
            "average_heartrate": int(self.average_heartrate)
            if self.average_heartrate
            else None,
            "map": run_map(self.polyline_str),
            "start_latlng": self.start_latlng,
            "source": self.source,
        }
        d.update(self.moving_dict)
        # return a nametuple that can use . to get attr
        return namedtuple("x", d.keys())(*d.values())
