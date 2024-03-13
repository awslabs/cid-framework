"""
This utility realigns new Athena table partitions to the original type in the event that an API call
returns a datatype that does not match the type from the initial crawler run.

Usage:
    Determine the name of your database and the table you wish to alter:

    python3 {prog} <database_name> <table_name>

"""
import sys
import logging
import boto3

logger = logging.getLogger(__name__)

def realign_partitions(database_name, table_name):
    logger.info(f"Realigning partitions for {database_name}.{table_name}")

    glue_client = boto3.client("glue")

    # Get the data types of the base table
    table_response = glue_client.get_table(
        DatabaseName=database_name,
        Name=table_name
    )

    column_to_datatype = {
        item["Name"]: item["Type"] for item in table_response["Table"]["StorageDescriptor"]["Columns"]
    }

    # List partitions and datatypes
    partition_params = {
        "DatabaseName": database_name,
        "TableName": table_name,
    }
    response = glue_client.get_partitions(**partition_params)
    partitions = response["Partitions"]

    while "NextToken" in response:
        partition_params["NextToken"] = response["NextToken"]
        response = glue_client.get_partitions(**partition_params)

        partitions += response["Partitions"]

    logger.debug(f"Found {len(partitions)} partitions")

    partitions_to_update = []
    for partition in partitions:
        changed = False
        columns = partition["StorageDescriptor"]["Columns"]
        new_columns = []
        for column in columns:
            if column["Name"] in column_to_datatype and column["Type"] != column_to_datatype[column["Name"]]:
                changed = True
                logger.debug(f"Changing type of {column['Name']} from {column['Type']} to {column_to_datatype[column['Name']]}")
                column["Type"] = column_to_datatype[column["Name"]]
            new_columns.append(column)
        partition["StorageDescriptor"]["Columns"] = new_columns
        if changed:
            partitions_to_update.append(partition)

    logger.debug(f"{len(partitions_to_update)} partitions of table {table_name} will be updated.")

    # Update partitions if necessary
    for partition in partitions_to_update:
        logger.debug(f"Updating {', '.join(partition['Values'])}")
        partition.pop("CatalogId")
        partition.pop("CreationTime")
        glue_client.update_partition(
            DatabaseName=partition.pop("DatabaseName"),
            TableName=partition.pop("TableName"),
            PartitionValueList=partition['Values'],
            PartitionInput=partition
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    logger.setLevel(logging.DEBUG)
    try:
        database_name = sys.argv[1]
        table_name = sys.argv[2]
    except:
        print(__doc__.format(prog=sys.argv[0]))
        exit(1)
    realign_partitions(database_name, table_name)