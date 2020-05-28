from . import schema


class ScalityDisk(schema.ScalityDisk):

    status_values_maps = {
        0: 'OK',
        3: 'WARNING',
        5: 'CRITICAL',
    }

    state_values_maps = {
        0: 'OK',
    }

    def get_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('disk_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.status_values_maps:
            return self.status_values_maps.get(value)
        return 'Undefined'

    def get_state(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('disk_state')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.state_values_maps:
            return self.state_values_maps.get(value)
        return 'Undefined'
