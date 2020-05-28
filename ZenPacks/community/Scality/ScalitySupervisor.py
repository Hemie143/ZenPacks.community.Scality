from . import schema


class ScalitySupervisor(schema.ScalitySupervisor):

    sup_status_values_maps = {
        3: 'Unknown',
        2: 'Invalid BizstoreSup credentials',
        1: 'Unreachable',
        0: 'Running',
    }

    def get_supv2_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('supervisor_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.sup_status_values_maps:
            return self.sup_status_values_maps.get(value)
        return 'Undefined'

    def get_bizstoresup_status(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('supervisor_bizstore_status')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.sup_status_values_maps:
            return self.sup_status_values_maps.get(value)
        return 'Undefined'
