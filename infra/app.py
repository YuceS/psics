from aws_cdk import App
from stacks.ps_stack import SimpleAppStack

app = App()

stack_prefix = "CDK-code-smells-"

code_smells_app = SimpleAppStack(
    app,
    f"{stack_prefix}CodeSmellsApp",
)
app.synth()
