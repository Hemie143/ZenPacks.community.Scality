from . import schema


class ScalityNode(schema.ScalityNode):

    state_values_maps = {
        0: 'OK',
    }

    def get_state(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('node_state')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.state_values_maps:
            return self.state_values_maps.get(value)
        return 'Undefined'
