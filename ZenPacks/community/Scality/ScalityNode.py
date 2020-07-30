from . import schema


class ScalityNode(schema.ScalityNode):

    state_values_maps = {
        0: 'RUN',
        1: 'AVAILABLE',
        2: 'NEW',
        3: 'TASKS_BLOCKED',
        4: 'LOOP',
        5: 'LOADING',
        6: 'LEAVING',
        7: 'DSO CHANGING',
        8: 'SPLIT',
        9: 'CONF_MISMATCH',
        10: 'ARC_REBUILD_NOK',
        11: 'BAL(SRC)',
        12: 'BAL(DST)',
        13: 'OUT_OF_SERVICE',
        14: 'NEED_RELOAD',
        15: 'DISKERR',
        16: 'DISKOFFLINE',
        17: 'DISKWARN',
        18: 'OFFLINE',
        19: 'DUPKEY',
        20: 'DISKFULL',
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
