from . import schema


class ScalityConnector(schema.ScalityConnector):

    status_values_maps = {
        0: 'OK',
        3: 'WARNING',
        5: 'CRITICAL',
    }

    state_values_maps = {
        0: 'OK',
        1: 'NEED RELOAD',
        2: 'CONFIG MISMATCH',
        3: 'DOWN/OFFLINE',
    }

    def get_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('connector_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.status_values_maps:
            return self.status_values_maps.get(value)
        return 'Undefined'

    def get_state(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('connector_state')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.state_values_maps:
            return self.state_values_maps.get(value)
        return 'Undefined'
