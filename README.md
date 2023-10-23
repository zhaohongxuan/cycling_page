## note1: use v2.0 need change vercel setting from Gatsby to Vite

## note2: 2023.09.26 garmin need secret_string(and in Actions) get `python run_page/garmin_sync.py ${secret_string}` if cn `python run_page/garmin_sync.py ${secret_string} --is-cn`


# [Create a personal workouts home page](http://workouts.ben29.xyz) 

[简体中文](README-CN.md) | English

This project is based on [running_page](https://github.com/yihong0618/running_page), add support for multi sports type. Follow the steps in origin repo to deploy.


## New Features
1. support multi sports type, like Ride/Hike/Swim/Rowing



## Custom your page

### Change Sports Color

* Modify Ride Color: `RIDE_COLOR` in `src/utils/const.js` 

### Add Sports Type

* Modify `TYPE_DICT` in  `scripts/config.py`
* Modify `colorFromType` in  `src/utils/util.js` 

---

# Special thanks
- @[yihong0618](https://github.com/yihong0618) for Awesome [running_page](https://github.com/yihong0618/running_page) , Great Thanks
