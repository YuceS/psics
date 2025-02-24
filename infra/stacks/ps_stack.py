from aws_cdk import SecretValue, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_iam as iam
from aws_cdk import aws_rds as rds
from constructs import Construct

# I added fixme and todo tagged comments.
# TODO Please check with the app team how they will deploy the app to the machine. Some questions are below 
# 1- They might need ssh access, ssm access, or a deployment agent installed to the machine or a user data script.
# 2- Is the database definitely be public? if yes, any ip whitelistinmg could be required. Usually, they have db migration code/scripts to iniate the db, then the db does not need to be publicly exposed.
# 3- If this is a production app, we need to have a load balancer infront of the app servers, a second app server, 

# For the rest, please see the comments inline. Overall code looks very structured and satisfies the standards. I just need to share some basic principles we follow here like the ones below.
# 1- Least privileged access via AWS IAM or AWS Secrets Manager
# 2- Whitelisted network access for communication via EC2 Security groups, Network ACLs and subnets. That includes publicly exposed ports and the communication between services and instances. There is a very good example here, https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.RDSSecurityGroups.html#Overview.RDSSecurityGroups.Scenarios
#   - This also implies that no full access to the internet can not be allowed from any service or instance.


class SimpleAppStack(Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        #FIXME Please define all the hardcoded values like port numbers, disk sizes, db name, define here with self explaining var names. So they can reused multiple times or reset easily
        # You can also initiate soem of these vars with arguments, those most likely to be requested for cahnge like db name, diosk size could easily be passed via arguments.
        self.vpc = ec2.Vpc(
            self,
            #FIXME use the id as a prefix to any resource name you create. Or you can add tags with the id.
            "Vpc",
            # TODO Check if this is too wide. Eventually, our environment is going to have 2 active ip addresses, an app server and a db.
            ip_addresses=ec2.IpAddresses.cidr("192.179.0.0/16"),
            #For production workloads, we usually use at least 3 to follow 2n+1 
            max_azs=2,
            subnet_configuration=[
            # FIXME we also need a private subnet for the RDS instance. Please add one more subnet configuration of type ec2.SubnetType.PRIVATE_ISOLATED
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        # Security Group for RDS
        self.db_security_group = ec2.SecurityGroup(
            self,
            "DbSecurityGroup",
            vpc=self.vpc,
            description="Allow access to DbInstance",
            # FIXME please dont allow all outbound true ever for anything. As security groups are stateful, the database is already able to respond to the instance through the inbound connection.
            allow_all_outbound=True,
        )
        self.db_security_group.add_ingress_rule(
        # FIXME Whitelist to inbound traffic to database port only and to the ec2 instance. You can use the reference to the SG assignmed to the instance. This is very similar to line 111 
            peer=ec2.Peer.any_ipv4(), connection=ec2.Port.all_traffic()
        )

        # RDS Subnet Group
        rds_subnet_group = rds.SubnetGroup(
            self,
            "DBSubnetGroup",
            description="DBSubnetGroup",
            vpc=self.vpc,
            # FIXME Use only private subnets for databases. We do not want to expose our database to the internet.
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
        )

        # RDS Instance
        rds.DatabaseInstance(
            self,
            # FIXME Please follow the naming conventions that employs the team and the app name.
            "DbInstance",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_16_4
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE2, ec2.InstanceSize.MICRO
            ),
            credentials=rds.Credentials.from_password(
            # FIXME please never hardcode password into the code. 
            # - use AWS IAM like defined here https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/UsingWithRDS.IAMDBAuth.html
            # - if not possible, use AWS Secrets Manager to hold the password
                username="admin", password=SecretValue.unsafe_plain_text("HelL0w0rLD")
            ),
            vpc=self.vpc,
            # FIXME Please do not use public subnets for the database, instead choose ec2.SubnetType.PRIVATE_ISOLATED,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[self.db_security_group],
            # FIXME do not make the databases publicly accessible. Check https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_VPC.WorkingWithRDSInstanceinaVPC.html#USER_VPC.Hiding
            publicly_accessible=True,
            subnet_group=rds_subnet_group,
            database_name="Db",
            allocated_storage=50,
        )

        # Security Group for EC2
        # FIXME should be self.ec2_security_group, we may need setter and getter for this resource.This is very similar to what you have done on  line 53 with teh db security group
        my_ec2_security_group = ec2.SecurityGroup(
            self,
            "Ec2SecurityGroup",
            vpc=self.vpc,
            # TODO you can mention the type of access here, https
            description="Allow access to Ec2Instance",
            allow_all_outbound=False,
        )
        my_ec2_security_group.add_ingress_rule(
            peer=ec2.Peer.any_ipv4(), connection=ec2.Port.tcp(443)
        )
        my_ec2_security_group.add_egress_rule(
            # TODO Please check with the app team if they need access to the internet or some public APIs
            peer=self.db_security_group, connection=ec2.Port.tcp(5432)
        )

        # EC2 Instance
        self.ec2_instance = ec2.Instance(
            self,
            "Ec2Instance",
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE4_GRAVITON, ec2.InstanceSize.MICRO
            ),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_group=my_ec2_security_group,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/sda1",
                    volume=ec2.BlockDeviceVolume.ebs(
                        8, volume_type=ec2.EbsDeviceVolumeType.GP3
                    ),
                )
            ],
        )

        # IAM Role for EC2 Instance
        self.iam_role = iam.Role(
            self,
            # FIXME we always define a meaningful name for the IAM roles as they are periodcially reviewed by security team.
            "IamRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[
                # FIXME Please never, ever give an administrator access to any publicly exposed machine.
                # Why do you need an EC2 permissions? Are you planning to create more machines calling aws apis from this machine ?
                iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
                # Add the database access here, if possible. If not add access to the secret store.
                # Please always limit the resources on an iam policy to the resources created within the stack. We always ollow least-privileged access https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html#grant-least-privilege
            ],
        )

        # FIXME Attach the Role to the EC2 instance like self.ec2_instance.role = self.iam_role 
        self.ec2_instance.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("AdministratorAccess")
        )
