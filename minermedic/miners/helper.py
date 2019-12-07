# helper.py, Copyright (c) 2019, Nicholas Saparoff <nick.saparoff@gmail.com>: Original implementation

from phenome_core.core.base.logger import root_logger as logger
from phenome_core.util.power import get_kilowatt_minute_cost
from phenome_core.core.globals import datamodel_maps
from phenome_core.core.helpers.model_helpers import get_units_id_by_symbol

datamodel_hashrate_units = None

"""

Miner Helper functions 

Contains a number of functions to help with parsing results, hashrates, power, etc.

"""

UNIT_MULTIPLIERS = {'Y': 1000000000000000, 'Z': 1000000000000, 'E': 1000000000, 'P': 1000000, 'T': 1000, 'G': 1,
                    'M': 0.001, 'K': 0.000001, '-': 0.000000001}


def parse_worker_string(miner, worker):

    """
    Parses a worker string and returns the coin address and worker ID

    Returns:
        String, String
    """

    worker_part_count = worker.count(".") + 1

    if worker_part_count > 1:
        if worker_part_count == 2:
            coin_address, worker = worker.split('.')
        else:
            worker_parts = worker.split('.')
            coin_address = worker_parts[0]
            worker = worker_parts[worker_part_count - 1]
    else:
        coin_address = worker

    if coin_address is not None:
        if miner.coin_address is None or len(miner.coin_address) == 0:
            miner.coin_address = coin_address
        elif miner.coin_address != coin_address:
            miner.coin_address = coin_address

    if worker is not None:
        if miner.worker_name is None or len(miner.worker_name) == 0:
            miner.worker_name = worker
        elif miner.worker_name != worker:
            miner.worker_name = worker

    return coin_address, worker


def __get_size_unit(unit):

    if unit is None:
        return None

    convert_unit = unit.upper()
    if convert_unit[-2:] != "/S":
        convert_unit = convert_unit + "/S"

    # remove H/S and SOLS/S (the only two units of work I know of in crypto)
    size_unit = convert_unit.replace("H/S","")
    size_unit = size_unit.replace("SOLS/S","")
    if size_unit == '':
        size_unit = "-"

    return size_unit

def get_normalized_gigahash_per_sec_from_hashrate(value, unit):

    """
    Takes passed hashrate in any units, converts to GH/s.

    Returns:
        Integer

    """

    # convert to GH/s
    value = value * UNIT_MULTIPLIERS[__get_size_unit(unit)]

    return value


def get_normalized_hashrate_from_gigahash_per_sec(value, unit):

    """
    Normalizes hashrate from GH/s to any other units.

    Returns:
        Float, String
    """

    # convert FROM GH/s
    value = value / UNIT_MULTIPLIERS[__get_size_unit(unit)]

    # nicely format those units!
    units_clean = unit.replace("/S","/s")

    # return both
    return value, units_clean


def get_hashrate_info(results, miner, algo):

    """
    Get Hashrate Information for a particular Miner and Algo

    Returns:
        dict

    """

    # do the lookup
    hashrate_info = results.get_hashrate_info(miner, algo)

    if hashrate_info is None:
        logger.warning("Model/Algo combination does not exist for "
                       "miner model '{}' and algo '{}'".format(miner.model.model, algo))

    return hashrate_info


def get_converted_hashrate(original_value, original_units, new_units):

    """
    Converts any hashrate from Units A to Units B

    Returns:
        Integer

    """

    if original_value is None or original_units is None or new_units is None:
        return None

    # get the current_hashrate_pool from the conversion method
    original_ghs = get_normalized_gigahash_per_sec_from_hashrate(original_value, original_units)

    # now normalize to expected hashrate units
    new_hashrate, units = get_normalized_hashrate_from_gigahash_per_sec(original_ghs, new_units)

    return new_hashrate


def get_power_usage_info_per_algo_per_minute(results, miner, algo):

    """
    Determines Miner Power Usage Per Algo Per Minute

    Returns:
        Integer, Integer - Power Used Per Minute (Watts), and Cost of Power Used Per Minute

    """

    # first, find out if we can get it from the miner
    watt_hours = miner.get_power_usage_watts()

    if watt_hours == 0:
        # get the current power needed for this miner using this algo
        hashrate_info = get_hashrate_info(results, miner, algo)
        if hashrate_info is not None:
            watt_hours = hashrate_info['power']

    if watt_hours is None or watt_hours == 0:
        return None, None

    # get power used per minute
    power_used_per_minute = watt_hours / 60

    # convert to kilowatt hours and multiply times cost per kilowatt minute
    power_used_cost_per_minute =  (watt_hours / 1000) * get_kilowatt_minute_cost()

    # return amount used per minute and cost per minute
    return power_used_per_minute, power_used_cost_per_minute


def calculate_hashrates(results, miner, hashrate_ghs5s, algo):

    """
    Calculates Hashrates for a miner based on the Algo and a passed Hashrate in GH/s.
    Stores values in the Miner Results Object.

    Returns:
        None

    """

    # first get the hashrate info for this ALGO on this MODEL miner
    hashrate_info = get_hashrate_info(results, miner, algo)

    if hashrate_info is None:
        return

    # get the current hashrate and units, normalized to what this device and algo are set to in the model
    current_hashrate, hashrate_units = \
        get_normalized_hashrate_from_gigahash_per_sec(hashrate_ghs5s, hashrate_info['units'])

    # get the expected hashrate
    expected_hashrate = hashrate_info['expected_rate']

    # if zero, set it to the rate...
    if expected_hashrate == 0:
        expected_hashrate = miner.hashrate[0]['rate']

    # update all detailed hashrate stats for this miner
    results.set_result(miner, 'hashrates', {'current': current_hashrate, 'max': expected_hashrate,
                                            'units': hashrate_units, 'algo': algo})

    try:

        # update the normalized hashrate results using the global hashrate
        datamodel_hashrate, calculated_units = \
            get_normalized_hashrate_from_gigahash_per_sec(hashrate_ghs5s, get_normalized_global_hashrate())

        units_id = get_units_id_by_symbol(calculated_units)

        # set the normalized result
        results.set_result(miner, 'hashrate', datamodel_hashrate)
        results.set_result(miner, 'hashrate_units', units_id)

    except:
        pass

    # FOR HASHRATE PER MODEL -->

    # add in the total hash_rate_per_model
    hashrate_info["sum_current"] += current_hashrate

    # set the units
    hashrate_info["unit"] = hashrate_units

    # add max for this model
    hashrate_info["sum_max"] += expected_hashrate

    # TODO - ACCEPTED HASHRATE PER ALGO / POOL


def get_normalized_global_hashrate():

    """
    The CRYPTO_MINER datamodel has a HashRate setting. We must use this setting
    to normalize the current HASHRATE stats so that we have a standard, normalized
    setting in all of our results.

    :return: String

    """

    global datamodel_hashrate_units

    if datamodel_hashrate_units is None:

        try:
            # we need to get them from the datamodel
            datamodel_hashrate_units = datamodel_maps['CRYPTO_MINER']['hashrate']['default'][0]['units']
        except:
            pass

        if datamodel_hashrate_units is None:
            # default to MH/s for this application
            datamodel_hashrate_units = "MH/s"

    return datamodel_hashrate_units