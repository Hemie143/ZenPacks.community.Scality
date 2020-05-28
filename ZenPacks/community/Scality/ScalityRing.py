from . import schema


class ScalityRing(schema.ScalityRing):

    status_values_maps = {
        5: 'CRITICAL',
        3: 'WARNING',
        0: 'OK',
    }

    state_values_maps = {
        0: 'RUN',                   # OK
        1: 'BALANCING',             # WARNING
        2: 'CONFIG MISMATCH',
        3: 'OFFLINE',
        4: 'DISK USAGE WARNING',
        5: 'LOW STORAGE',
        6: 'ARC_REBUILD_NOK',       # WARNING / CRITICAL
        7: 'MISSING NODE',          # CRITICAL
        8: 'INCOMPLETE',
        9: 'NOT STABILIZED',
        10: 'OUT OF SERVICE',
        11: 'DUPLICATE KEY',
        12: 'DISK FULL',
        13: 'SPLIT',
        14: 'LOOP',
    }

    def get_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('ring_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.status_values_maps:
            return self.status_values_maps.get(value)
        return 'Undefined'

    def get_state(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('ring_state')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.state_values_maps:
            return self.state_values_maps.get(value)
        return 'Undefined'
