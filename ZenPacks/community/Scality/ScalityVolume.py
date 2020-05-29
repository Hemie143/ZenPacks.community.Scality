from . import schema


class ScalityVolume(schema.ScalityVolume):

    status_value_maps = {
        0: 'OK',
        1: 'WARNING',
        2: 'NO CONNECTOR',
        3: 'CRITICAL',
    }

    def get_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('volume_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.status_value_maps:
            return self.status_value_maps.get(value)
        return 'Undefined'
