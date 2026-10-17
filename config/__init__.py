"""
Si usas `pip install mysqlclient` no necesitas esto. Pero mysqlclient a
veces da problemas al compilar según el sistema operativo; con pymysql
como alternativa (`pip install pymysql`), estas dos líneas hacen que
Django lo use como si fuera MySQLdb.
"""
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass
