from . import schema


class ScalityS3Cluster(schema.ScalityS3Cluster):

    health_values_maps = {
        0: 'NOMINAL',
    }

    def get_cluster_health(self):
        """return string interpretation of an integer value"""
        value = self.cacheRRDValue('s3cluster_health')
        try:
            value = int(value)
        except ValueError:
            return 'Unknown'
        if value in self.health_values_maps:
            return self.health_values_maps.get(value)
        return 'Undefined'
