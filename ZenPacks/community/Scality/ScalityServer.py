from . import schema


class ScalityServer(schema.ScalityServer):

    status_values_maps = {
        5: 'CRITICAL',
        3: 'WARNING',
        0: 'OK',
    }

    state_values_maps = {
        0: 'ONLINE',
        1: 'MISSING',
        2: 'OFFLINE',
    }


    def get_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('server_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.status_values_maps:
            return self.status_values_maps.get(value)
        return 'Undefined'

    def get_state(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('server_state')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.state_values_maps:
            return self.state_values_maps.get(value)
        return 'Undefined'
